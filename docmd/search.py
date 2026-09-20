"""Keyword search across pre-converted RAG chunk files - `docmd search
<dir> "query"`.

Searches structured chunk JSON already produced by `docmd batch --format
rag`, not raw documents - repeated searches don't reconvert anything, and
this module has no dependency on Marker or any conversion machinery at all.

Keyword matching, not semantic search: scores each chunk by how many query
words it contains, plus a bonus for an exact phrase match. This won't find
conceptually related text that doesn't share words with the query (e.g. a
query for "revenue" won't match a chunk that only says "income"). A
semantic mode is real future scope, gated the same way `ConvertConfig.use_llm`
already gates another capability that needs a real provider key to build and
test against - not something to fake with an untested embedding call.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from docmd.converters.base import Chunk

_WORD_RE = re.compile(r"\w+")
_EXACT_PHRASE_BONUS = 5.0


@dataclass
class SearchResult:
    source: str
    """Path of the chunk file this result came from, relative to the
    directory `search()` was called with."""
    chunk: Chunk
    score: float


def _tokenize(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def _score(query_words: list[str], query_phrase: str, text: str) -> float:
    text_words = _tokenize(text)
    score = float(sum(text_words.count(word) for word in query_words))
    if query_phrase in text.lower():
        score += _EXACT_PHRASE_BONUS
    return score


def _load_chunks(json_path: Path) -> list[Chunk]:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    return [
        Chunk(
            text=item["text"],
            page=item["page"],
            section=item["section"],
            content_type=item["content_type"],
            bbox=tuple(item["bbox"]),
        )
        for item in data
    ]


def search(directory: Path, query: str, limit: int = 10) -> list[SearchResult]:
    """Searches every `.json` chunk file under `directory` for `query`,
    ranked by keyword relevance, highest first."""
    query_words = _tokenize(query)
    if not query_words:
        return []
    query_phrase = query.lower()

    results: list[SearchResult] = []
    for json_path in sorted(directory.rglob("*.json")):
        try:
            chunks = _load_chunks(json_path)
        except (json.JSONDecodeError, TypeError, KeyError):
            # Not a chunk file docmd produced (or produced by a version with
            # a different shape) - skip it rather than crashing the whole
            # search over one unrelated or stale file.
            continue

        for chunk in chunks:
            score = _score(query_words, query_phrase, chunk.text)
            if score > 0:
                results.append(
                    SearchResult(source=str(json_path.relative_to(directory)), chunk=chunk, score=score)
                )

    results.sort(key=lambda r: r.score, reverse=True)
    return results[:limit]
