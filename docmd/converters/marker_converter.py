"""Wraps `marker-pdf` (https://github.com/datalab-to/marker) as a docmd Converter.

Uses Marker's Python API directly (not its CLI/server) so we control input and
output cleanly. `PdfConverter` is Marker's general-purpose converter despite
the name: it dispatches to the right internal provider (PDF, DOCX, PPTX, ...)
based on the file's actual content, via `provider_from_filepath`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from docmd.config import ConvertConfig
from docmd.converters.base import ConversionResult
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

        try:
            converter = PdfConverter(
                config=config_dict,
                artifact_dict=_get_model_dict(),
                processor_list=config_parser.get_processors(),
                renderer=config_parser.get_renderer(),
                llm_service=config_parser.get_llm_service(),
            )
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

        markdown, _, images = text_from_rendered(rendered)
        metadata = dict(getattr(rendered, "metadata", {}) or {})
        page_count = len(metadata.get("page_stats", [])) or 1

        return ConversionResult(
            markdown=markdown,
            page_count=page_count,
            images=images,
            metadata=metadata,
        )
