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


def test_short_chunk_defining_a_rare_term_outranks_a_long_chunk_repeating_a_common_one(tmp_path):
    """Found running search against a real arXiv paper: for "self-attention"
    the top hit was a long bullet that repeats "attention" many times, ahead
    of the short chunk that actually defines self-attention. Raw word counts
    can't tell those apart; BM25's rare-term weighting and length
    normalization can."""
    filler = [_chunk(f"Unrelated filler paragraph number {i} about other topics entirely") for i in range(10)]
    long_repeater = "attention " * 6 + "and then a lot of other words " * 10
    _write_chunks(
        tmp_path / "doc.json",
        [
            *filler,
            _chunk(long_repeater),
            _chunk("Self-attention is a mechanism relating positions of a sequence"),
        ],
    )
    results = search(tmp_path, "self attention")
    assert results[0].chunk.text.startswith("Self-attention is a mechanism")


def test_repeated_query_words_are_not_double_counted(tmp_path):
    """"revenue revenue" must score like "revenue", not double. The only
    legitimate difference is the exact-phrase bonus, which the one-word query
    earns (its phrase is in the text) and the repeated-word query doesn't."""
    from docmd.search import _EXACT_PHRASE_BONUS

    _write_chunks(tmp_path / "doc.json", [_chunk("revenue growth"), _chunk("revenue")])
    once = search(tmp_path, "revenue")
    twice = search(tmp_path, "revenue revenue")
    assert [r.chunk.text for r in once] == [r.chunk.text for r in twice]
    assert [round(r.score - _EXACT_PHRASE_BONUS, 6) for r in once] == [round(r.score, 6) for r in twice]
