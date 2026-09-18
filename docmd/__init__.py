"""docmd: convert PDF/DOCX/PPTX to clean, structure-preserving Markdown.

    from docmd import convert
    markdown = convert("report.pdf")
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from docmd.config import ConvertConfig
from docmd.converters.base import ConversionResult
from docmd.converters.registry import get_converter
from docmd.postprocess.heading_normalize import normalize_headings
from docmd.postprocess.image_handling import apply_image_handling
from docmd.postprocess.table_cleanup import clean_tables

__all__ = ["convert", "convert_document", "ConvertConfig", "ConversionResult"]
__version__ = "0.1.0"


def convert_document(
    source: str | Path | bytes,
    *,
    filename: str | None = None,
    config: ConvertConfig | None = None,
) -> ConversionResult:
    """Convert `source` and return the full result (markdown + page count +
    metadata), after docmd's post-processing pass has run.

    `source` is either a path to a file, or raw bytes - in which case
    `filename` is required so docmd knows the format (its extension is used
    to pick a converter; the content itself is what gets converted).
    """
    config = config or ConvertConfig()

    if isinstance(source, (bytes, bytearray)):
        if not filename:
            raise ValueError("filename is required when passing bytes")
        suffix = Path(filename).suffix
        fd, tmp_path = tempfile.mkstemp(suffix=suffix)
        try:
            with os.fdopen(fd, "wb") as tmp:
                tmp.write(source)
            result = _convert_path(tmp_path, config)
        finally:
            os.unlink(tmp_path)
    else:
        result = _convert_path(str(source), config)

    return result


def convert(
    source: str | Path | bytes,
    *,
    filename: str | None = None,
    config: ConvertConfig | None = None,
) -> str:
    """Convert `source` (a file path, or bytes + filename) and return the
    resulting Markdown as a string."""
    return convert_document(source, filename=filename, config=config).markdown


def _convert_path(filepath: str, config: ConvertConfig) -> ConversionResult:
    converter = get_converter(filepath)
    result = converter.convert(filepath, config)

    markdown = result.markdown
    if config.clean_tables:
        markdown = clean_tables(markdown)
    if config.normalize_headings:
        markdown = normalize_headings(markdown)
    markdown = apply_image_handling(markdown, result.images, config.image_mode)

    return ConversionResult(
        markdown=markdown,
        page_count=result.page_count,
        images=result.images,
        metadata=result.metadata,
    )
