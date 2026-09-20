"""Tests for ConvertConfig.include_chunks / ConversionResult.chunks - see
docmd/converters/chunk_extraction.py and docmd/converters/base.py:Chunk.
"""

from __future__ import annotations

from pathlib import Path

from docmd import convert_document
from docmd.config import ConvertConfig
from docmd.converters.base import CONTENT_TYPES

FIXTURES = Path(__file__).parent / "fixtures"


def test_chunks_are_none_by_default():
    result = convert_document(str(FIXTURES / "sample.pdf"))
    assert result.chunks is None


def test_chunks_cover_headings_and_body_text_in_reading_order():
    result = convert_document(
        str(FIXTURES / "running_header.pdf"), config=ConvertConfig(include_chunks=True)
    )
    content_types = [c.content_type for c in result.chunks]
    assert content_types == [
        "heading",
        "heading",
        "text",
        "heading",
        "text",
        "heading",
        "text",
        "heading",
        "text",
    ]


def test_repeated_running_header_is_excluded_from_chunks():
    """The same real Marker defect test_running_header_does_not_leak_into_output
    guards against at the Markdown level: a page header repeated on every
    page (sometimes misclassified as a heading on later pages) must not
    show up as its own chunk, on any page."""
    result = convert_document(
        str(FIXTURES / "running_header.pdf"), config=ConvertConfig(include_chunks=True)
    )
    assert all("CONFIDENTIAL" not in c.text for c in result.chunks)


def test_section_breadcrumb_reflects_heading_hierarchy():
    result = convert_document(
        str(FIXTURES / "running_header.pdf"), config=ConvertConfig(include_chunks=True)
    )
    body_chunks = [c for c in result.chunks if c.content_type == "text"]
    assert body_chunks[0].section == "Quarterly Risk Review > Section 1: Findings"
    assert body_chunks[1].section == "Quarterly Risk Review > Section 2: Findings"


def test_chunks_carry_correct_page_numbers():
    result = convert_document(
        str(FIXTURES / "running_header.pdf"), config=ConvertConfig(include_chunks=True)
    )
    body_chunks = [c for c in result.chunks if c.content_type == "text"]
    assert [c.page for c in body_chunks] == [0, 1, 2, 3]


def test_table_chunk_has_table_content_type_and_real_bbox():
    result = convert_document(str(FIXTURES / "stress.pdf"), config=ConvertConfig(include_chunks=True))
    table_chunks = [c for c in result.chunks if c.content_type == "table"]
    assert len(table_chunks) >= 1
    for chunk in table_chunks:
        assert chunk.bbox != (0.0, 0.0, 0.0, 0.0)
        assert chunk.text  # Marker's own flattened cell text, not empty


def test_image_block_produces_a_chunk_with_empty_text():
    """Found while building this: image blocks have no raw_text() at all,
    so the "skip if no text" rule that correctly drops empty text/table
    blocks would also silently drop every image chunk. Images still get a
    chunk - with real page/section/bbox metadata - just an empty text
    field, rather than being dropped entirely."""
    result = convert_document(str(FIXTURES / "with_image.pdf"), config=ConvertConfig(include_chunks=True))
    image_chunks = [c for c in result.chunks if c.content_type == "image"]
    assert len(image_chunks) == 1
    assert image_chunks[0].text == ""
    assert image_chunks[0].bbox != (0.0, 0.0, 0.0, 0.0)


def test_all_content_types_are_in_the_stable_vocabulary():
    for fixture in ["sample.pdf", "stress.pdf", "running_header.pdf", "with_image.pdf", "merged_cells.pdf"]:
        result = convert_document(str(FIXTURES / fixture), config=ConvertConfig(include_chunks=True))
        for chunk in result.chunks:
            assert chunk.content_type in CONTENT_TYPES, (
                f"{fixture}: {chunk.content_type!r} not in the stable vocabulary"
            )
