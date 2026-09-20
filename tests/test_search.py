"""Tests for docmd/search.py (docmd search) - pure function over chunk JSON
files on disk, no PDF/Marker conversion involved."""

from __future__ import annotations

import json

from docmd.search import search


def _write_chunks(path, chunks):
    path.write_text(json.dumps(chunks), encoding="utf-8")


def _chunk(text, page=0, section="", content_type="text", bbox=(0.0, 0.0, 1.0, 1.0)):
    return {"text": text, "page": page, "section": section, "content_type": content_type, "bbox": list(bbox)}


def test_finds_a_matching_chunk(tmp_path):
    _write_chunks(
        tmp_path / "doc.json",
        [_chunk("Revenue increased in 2024"), _chunk("Unrelated paragraph about weather")],
    )
    results = search(tmp_path, "revenue 2024")
    assert len(results) == 1
    assert results[0].chunk.text == "Revenue increased in 2024"
    assert results[0].source == "doc.json"


def test_ranks_more_relevant_chunks_first(tmp_path):
    _write_chunks(
        tmp_path / "doc.json",
        [
            _chunk("Revenue mentioned once here"),
            _chunk("Revenue revenue revenue - all about revenue"),
        ],
    )
    results = search(tmp_path, "revenue")
    assert results[0].chunk.text == "Revenue revenue revenue - all about revenue"


def test_exact_phrase_match_ranks_above_scattered_word_matches(tmp_path):
    _write_chunks(
        tmp_path / "doc.json",
        [
            _chunk("Some growth discussion. Separately, 2024 came up too, in a different place."),
            _chunk("Revenue growth in 2024 was strong."),
        ],
    )
    results = search(tmp_path, "growth in 2024")
    assert results[0].chunk.text == "Revenue growth in 2024 was strong."


def test_searches_across_multiple_files_and_tags_source(tmp_path):
    _write_chunks(tmp_path / "a.json", [_chunk("Apples are a fruit")])
    _write_chunks(tmp_path / "b.json", [_chunk("Bananas are also a fruit")])
    results = search(tmp_path, "fruit")
    sources = {r.source for r in results}
    assert sources == {"a.json", "b.json"}


def test_searches_nested_directories(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    _write_chunks(sub / "nested.json", [_chunk("Deeply nested revenue figures")])
    results = search(tmp_path, "revenue")
    assert len(results) == 1
    assert results[0].source == "sub/nested.json"


def test_no_matches_returns_empty_list(tmp_path):
    _write_chunks(tmp_path / "doc.json", [_chunk("Nothing relevant here")])
    assert search(tmp_path, "xyzzy_nonexistent_term") == []


def test_respects_limit(tmp_path):
    _write_chunks(tmp_path / "doc.json", [_chunk(f"revenue chunk {i}") for i in range(20)])
    results = search(tmp_path, "revenue", limit=5)
    assert len(results) == 5


def test_ignores_non_chunk_json_files(tmp_path):
    (tmp_path / "not_a_chunk_file.json").write_text('{"unrelated": "structure"}', encoding="utf-8")
    _write_chunks(tmp_path / "doc.json", [_chunk("revenue figures here")])
    results = search(tmp_path, "revenue")
    assert len(results) == 1
    assert results[0].source == "doc.json"


def test_empty_query_returns_no_results(tmp_path):
    _write_chunks(tmp_path / "doc.json", [_chunk("revenue figures here")])
    assert search(tmp_path, "   ") == []
