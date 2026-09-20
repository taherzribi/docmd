"""docmd: convert PDF/DOCX/PPTX to clean, structure-preserving Markdown.

    from docmd import convert
    markdown = convert("report.pdf")
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from docmd.config import ConvertConfig
from docmd.converters.base import Chunk, ConversionResult
from docmd.converters.registry import get_converter
from docmd.postprocess.heading_normalize import normalize_headings
from docmd.postprocess.image_handling import apply_image_handling
from docmd.postprocess.rtl_fix import fix_rtl_brackets
from docmd.postprocess.table_cleanup import clean_tables

__all__ = ["convert", "convert_document", "ConvertConfig", "ConversionResult", "Chunk"]
__version__ = "0.1.13"


def convert_document(
    source: str | Path | bytes,
    *,
    filename: str | None = None,
    config: ConvertConfig | None = None,
    output_dir: str | Path | None = None,
) -> ConversionResult:
    """Convert `source` and return the full result (markdown + page count +
    metadata), after docmd's post-processing pass has run.

    `source` is either a path to a file, or raw bytes - in which case
    `filename` is required so docmd knows the format (its extension is used
    to pick a converter; the content itself is what gets converted).

    `output_dir`: only meaningful with `config.image_mode == "alt-text"`,
    which keeps real image links in the output Markdown - those links only
    resolve if the image files actually exist somewhere, so pass the
    directory to save them into (typically wherever the output .md file is
    going). Without it, `alt-text` mode's links point to image filenames
    that were never written anywhere. `placeholder` (the default) and
    `skip` modes ignore this - they never reference image files at all.
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
            result = _convert_path(tmp_path, config, output_dir)
        finally:
            os.unlink(tmp_path)
    else:
        result = _convert_path(str(source), config, output_dir)

    return result


def convert(
    source: str | Path | bytes,
    *,
    filename: str | None = None,
    config: ConvertConfig | None = None,
    output_dir: str | Path | None = None,
) -> str:
    """Convert `source` (a file path, or bytes + filename) and return the
    resulting Markdown as a string. See `convert_document` re: `output_dir`."""
    return convert_document(source, filename=filename, config=config, output_dir=output_dir).markdown


def _convert_path(
    filepath: str, config: ConvertConfig, output_dir: str | Path | None
) -> ConversionResult:
    converter = get_converter(filepath)
    result = converter.convert(filepath, config)

    markdown = result.markdown
    if config.clean_tables:
        markdown = clean_tables(markdown)
    if config.normalize_headings:
        markdown = normalize_headings(markdown)
    if config.fix_rtl_brackets:
        markdown = fix_rtl_brackets(markdown)
    markdown = apply_image_handling(markdown, result.images, config.image_mode, output_dir)

    return ConversionResult(
        markdown=markdown,
        page_count=result.page_count,
        images=result.images,
        metadata=result.metadata,
        provenance=result.provenance,
        chunks=result.chunks,
    )
