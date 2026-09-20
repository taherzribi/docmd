"""Wraps `marker-pdf` (https://github.com/datalab-to/marker) as a docmd Converter.

Uses Marker's Python API directly (not its CLI/server) so we control input and
output cleanly. `PdfConverter` is Marker's general-purpose converter despite
the name: it dispatches to the right internal provider (PDF, DOCX, PPTX, ...)
based on the file's actual content, via `provider_from_filepath`.
"""

from __future__ import annotations

import importlib.metadata
import time
from pathlib import Path
from typing import Any

from docmd.config import ConvertConfig
from docmd.converters.base import ConversionResult
from docmd.converters.chunk_extraction import extract_chunks
from docmd.errors import (
    ConversionError,
    EncryptedDocumentError,
    MissingExtraError,
    MissingSystemDependencyError,
)

# Marker loads its models (a few hundred MB to ~1GB of weights, downloaded
# from Hugging Face on first use) lazily and caches them at module scope, so
# repeated conversions within one process don't reload them.
_model_dict: dict[str, Any] | None = None

_PASSWORD_HINTS = ("password", "encrypt")
# Raised as surya.inference.backends.spawn.SpawnError when OCR/equation
# recognition needs the llama-server binary and it isn't on PATH - matched
# by message/type name rather than importing surya's internal exception
# class, so this doesn't break if that module path moves.
_MISSING_BINARY_HINTS = ("llama-server", "spawnerror")


def _get_model_dict() -> dict[str, Any]:
    global _model_dict
    if _model_dict is None:
        from marker.models import create_model_dict

        _model_dict = create_model_dict()
    return _model_dict


_docmd_version_cache: str | None = None
_marker_version_cache: str | None = None


def _docmd_version() -> str:
    # Read from installed package metadata rather than `from docmd import
    # __version__` - that would import docmd/__init__.py, which imports
    # this module transitively (via the converter registry), a circular
    # import.
    global _docmd_version_cache
    if _docmd_version_cache is None:
        try:
            _docmd_version_cache = importlib.metadata.version("docmd-cli")
        except importlib.metadata.PackageNotFoundError:
            _docmd_version_cache = "unknown"
    return _docmd_version_cache


def _marker_version() -> str:
    global _marker_version_cache
    if _marker_version_cache is None:
        try:
            _marker_version_cache = importlib.metadata.version("marker-pdf")
        except importlib.metadata.PackageNotFoundError:
            _marker_version_cache = "unknown"
    return _marker_version_cache


def _build_config_dict(config: ConvertConfig):
    from marker.config.parser import ConfigParser

    options: dict[str, Any] = {
        "output_format": "markdown",
        "force_ocr": config.force_ocr,
        "use_llm": config.use_llm,
        # Marker's own default (4) spins up a multiprocessing.ProcessPoolExecutor
        # for page-text extraction on any sufficiently multi-page PDF. On
        # spawn-based platforms (macOS, Windows) that crashes with
        # "An attempt has been made to start a new process before the
        # current process has finished its bootstrapping phase" whenever the
        # caller isn't wrapped in `if __name__ == "__main__":` - an easy trap
        # for a library used from a plain script, a notebook, or a web
        # server's request handler. Marker's own bundled server.py sets this
        # to 1 for exactly this reason; docmd does the same as a library
        # default, trading a bit of extraction parallelism for not crashing
        # on arbitrary callers.
        "pdftext_workers": 1,
    }
    if config.image_mode == "skip":
        options["disable_image_extraction"] = True

    return ConfigParser(options)


class MarkerConverter:
    """Converter implementation backed by Marker."""

    def convert(self, filepath: str | Path, config: ConvertConfig) -> ConversionResult:
        filepath = str(filepath)
        try:
            from marker.converters.pdf import PdfConverter
            from marker.output import text_from_rendered
        except ImportError as exc:
            raise MissingExtraError(Path(filepath).suffix) from exc

        config_parser = _build_config_dict(config)
        config_dict = config_parser.generate_config_dict()

        start = time.monotonic()
        try:
            converter = PdfConverter(
                config=config_dict,
                artifact_dict=_get_model_dict(),
                processor_list=config_parser.get_processors(),
                renderer=config_parser.get_renderer(),
                llm_service=config_parser.get_llm_service(),
            )
            if config.include_chunks:
                # Same two steps PdfConverter.__call__() does internally -
                # done explicitly here so the pre-render Document (blocks,
                # pages, geometry) stays available for extract_chunks()
                # below, instead of being discarded once rendered to
                # Markdown. Not taken for the default case, so existing
                # callers see byte-identical behavior to before this existed.
                document = converter.build_document(filepath)
                renderer = converter.resolve_dependencies(converter.renderer)
                rendered = renderer(document)
            else:
                document = None
                rendered = converter(filepath)
        except Exception as exc:
            message = str(exc).lower()
            exc_type_name = type(exc).__name__.lower()
            if any(hint in message for hint in _PASSWORD_HINTS):
                raise EncryptedDocumentError() from exc
            if any(hint in message or hint in exc_type_name for hint in _MISSING_BINARY_HINTS):
                raise MissingSystemDependencyError(str(exc)) from exc
            raise ConversionError(
                f"Marker failed to convert '{filepath}': {exc}", cause=exc
            ) from exc

        duration_ms = int((time.monotonic() - start) * 1000)
        markdown, _, images = text_from_rendered(rendered)
        metadata = dict(getattr(rendered, "metadata", {}) or {})
        page_stats = metadata.get("page_stats", [])
        page_count = len(page_stats) or 1

        # A page whose text_extraction_method isn't "pdftext" went through
        # OCR/vision-based recognition rather than reading an embedded text
        # layer - independent of force_ocr, since Marker also falls back to
        # this per-page for a PDF with no usable text layer at all.
        ocr_used = config.force_ocr or any(
            page.get("text_extraction_method") != "pdftext" for page in page_stats
        )

        provenance = {
            "docmd_version": _docmd_version(),
            "backend": "marker",
            "backend_version": _marker_version(),
            "ocr_used": ocr_used,
            "conversion_duration_ms": duration_ms,
        }

        chunks = extract_chunks(document) if document is not None else None

        return ConversionResult(
            markdown=markdown,
            page_count=page_count,
            images=images,
            metadata=metadata,
            provenance=provenance,
            chunks=chunks,
        )
