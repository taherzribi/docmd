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
from docmd.errors import ConversionError, EncryptedDocumentError, MissingExtraError

# Marker loads its models (a few hundred MB to ~1GB of weights, downloaded
# from Hugging Face on first use) lazily and caches them at module scope, so
# repeated conversions within one process don't reload them.
_model_dict: dict[str, Any] | None = None

_PASSWORD_HINTS = ("password", "encrypt")


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
            if any(hint in message for hint in _PASSWORD_HINTS):
                raise EncryptedDocumentError() from exc
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
