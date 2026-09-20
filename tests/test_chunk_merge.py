"""Unit tests for docmd/converters/chunk_merge.py - pure function over
Chunk lists, no PDF/Marker needed. See tests/test_chunks.py for the
real-document integration tests (via ConvertConfig.chunk_max_tokens)."""

from __future__ import annotations

from docmd.converters.base import Chunk
from docmd.converters.chunk_merge import merge_chunks


def _chunk(text, page=0, section="", content_type="text", bbox=(0.0, 0.0, 10.0, 10.0)):
    return Chunk(text=text, page=page, section=section, content_type=content_type, bbox=bbox)


def test_merges_adjacent_text_chunks_within_budget():
    chunks = [_chunk("Hello"), _chunk("World")]
    result = merge_chunks(chunks, max_tokens=1000)
    assert len(result) == 1
    assert result[0].text == "Hello\n\nWorld"


def test_does_not_merge_across_a_section_boundary():
    chunks = [_chunk("Hello", section="A"), _chunk("World", section="B")]
    result = merge_chunks(chunks, max_tokens=1000)
    assert len(result) == 2
    assert [c.text for c in result] == ["Hello", "World"]


def test_does_not_merge_across_a_page_boundary():
    chunks = [_chunk("Hello", page=0), _chunk("World", page=1)]
    result = merge_chunks(chunks, max_tokens=1000)
    assert len(result) == 2


def test_never_merges_a_table_into_surrounding_text():
    chunks = [
        _chunk("before"),
        _chunk("R1 C1 R1 C2", content_type="table"),
        _chunk("after"),
    ]
    result = merge_chunks(chunks, max_tokens=1000)
    assert [c.content_type for c in result] == ["text", "table", "text"]
    assert result[1].text == "R1 C1 R1 C2"


def test_never_merges_an_image_chunk():
    chunks = [_chunk("before"), _chunk("", content_type="image"), _chunk("after")]
    result = merge_chunks(chunks, max_tokens=1000)
    assert [c.content_type for c in result] == ["text", "image", "text"]


def test_stops_merging_once_budget_would_be_exceeded():
    # "x" * 40 is ~10 tokens at the ~4 chars/token estimate: x+y fits in 25,
    # but x+y+z (~30) doesn't, so z starts a new group.
    chunks = [_chunk("x" * 40), _chunk("y" * 40), _chunk("z" * 40)]
    result = merge_chunks(chunks, max_tokens=25)
    assert len(result) == 2
    assert result[0].text == ("x" * 40) + "\n\n" + ("y" * 40)
    assert result[1].text == "z" * 40


def test_oversized_single_chunk_is_not_split():
    chunks = [_chunk("x" * 4000)]
    result = merge_chunks(chunks, max_tokens=10)
    assert len(result) == 1
    assert result[0].text == "x" * 4000


def test_merged_chunk_bbox_is_the_union_of_its_parts():
    chunks = [
        _chunk("a", bbox=(0.0, 0.0, 10.0, 10.0)),
        _chunk("b", bbox=(5.0, 5.0, 20.0, 20.0)),
    ]
    result = merge_chunks(chunks, max_tokens=1000)
    assert result[0].bbox == (0.0, 0.0, 20.0, 20.0)


def test_merged_chunk_keeps_first_subchunks_page_and_section():
    chunks = [_chunk("a", page=3, section="Ch. 1"), _chunk("b", page=3, section="Ch. 1")]
    result = merge_chunks(chunks, max_tokens=1000)
    assert result[0].page == 3
    assert result[0].section == "Ch. 1"


def test_empty_input_returns_empty_output():
    assert merge_chunks([], max_tokens=1000) == []
