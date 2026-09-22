"""Wraps `marker-pdf` (https://github.com/datalab-to/marker) as a docmd Converter.

Uses Marker's Python API directly (not its CLI/server) so we control input and
output cleanly. `PdfConverter` is Marker's general-purpose converter despite
the name: it dispatches to the right internal provider (PDF, DOCX, PPTX, ...)
based on the file's actual content, via `provider_from_filepath`.
"""

from __future__ import annotations

import importlib.metadata
import re
import time
from pathlib import Path
from typing import Any

from docmd.config import ConvertConfig
from docmd.converters.base import ConversionResult
from docmd.converters.chunk_extraction import extract_chunks
from docmd.converters.chunk_merge import merge_chunks
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


_SLIDE_HEADING_RE = re.compile(r"^Slide \d+$")


def _unsuppress_slide_headings(document: Any) -> None:
    r"""Undoes a real Marker bug found via real decks: IgnoreTextProcessor
    strips trailing digits before comparing text across pages
    (`re.sub(r"\s*\d+$", "", text)`), so "Slide 1", "Slide 2", "Slide 3" all
    collapse to the identical string "Slide" and get flagged as a repeated
    running header/footer - exactly the pattern that heuristic exists to
    catch, misfiring on the one heading docmd itself asked Marker to insert.
    ignore_for_output blocks are dropped before rendering (both Markdown and
    chunks never see them), so this has to run on the block tree, which is
    why PPTX always takes the two-step build+render path below, not just
    when chunks are requested. Only a heading whose text is exactly "Slide
    N" is touched - Marker's suppression of a real repeated header/footer
    elsewhere in the deck is left alone.

    Checked against every block type, not just SectionHeader: on one real
    deck, the "Slide 15" text was classified as a Caption block (Marker's
    layout model, not a text-content decision docmd controls) - the
    suppression bug and this fix for it are about the *text*, independent
    of whatever type Marker happened to assign it."""
    for page in document.pages:
        for block_id in page.structure or []:
            block = document.get_block(block_id)
            if not block.ignore_for_output:
                continue
            if _SLIDE_HEADING_RE.match((block.raw_text(document) or "").strip()):
                block.ignore_for_output = False


def _enable_slide_headings() -> None:
    """Turns on Marker's "Slide N" heading before each PPTX slide.

    Marker's PowerPoint provider concatenates every slide into one HTML
    document and renders that to a PDF, so slides flow onto pages by content
    height, not one per page: found via real decks where 34 slides became 15
    "pages" and 10 became 2. Without a heading per slide nothing marks where
    one starts, so neither Markdown sections nor chunk `page` numbers
    correspond to slides at all.

    Marker exposes this as `include_slide_number`, but passing it through the
    config dict cannot work in marker-pdf 2.0.0 (the pinned version): the
    provider builds its slide HTML in `convert_pptx_to_pdf`, which runs
    before `super().__init__()` applies the config, so `self.include_slide_number`
    is always the class default. Setting the class attribute is the only
    thing that takes effect.
    """
    from marker.providers.powerpoint import PowerPointProvider

    PowerPointProvider.include_slide_number = True


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

        if filepath.lower().endswith(".pptx"):
            _enable_slide_headings()

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
            is_pptx = filepath.lower().endswith(".pptx")
            if config.include_chunks or is_pptx:
                # Same two steps PdfConverter.__call__() does internally -
                # done explicitly here so the pre-render Document (blocks,
                # pages, geometry) is available: for extract_chunks() below
                # when chunks are requested, and unconditionally for PPTX so
                # _unsuppress_slide_headings() can run before ignore_for_output
                # blocks are dropped by the renderer. For any other case,
                # existing callers see byte-identical behavior to before
                # either of these existed.
                document = converter.build_document(filepath)
                if is_pptx:
                    _unsuppress_slide_headings(document)
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

        chunks = extract_chunks(document) if config.include_chunks and document is not None else None
        if chunks is not None and config.chunk_max_tokens is not None:
            chunks = merge_chunks(chunks, config.chunk_max_tokens)

        return ConversionResult(
            markdown=markdown,
            page_count=page_count,
            images=images,
            metadata=metadata,
            provenance=provenance,
            chunks=chunks,
        )
