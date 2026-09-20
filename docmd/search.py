"""Keyword search across pre-converted RAG chunk files - `docmd search
<dir> "query"`.

Searches structured chunk JSON already produced by `docmd batch --format
rag`, not raw documents - repeated searches don't reconvert anything, and
this module has no dependency on Marker or any conversion machinery at all.

Keyword matching, not semantic search, ranked with BM25: a term's weight
falls as it appears in more chunks (a rare word says more than a common
one), repeated occurrences saturate instead of growing without bound, and
long chunks are normalized against the corpus average so a big block that
merely repeats a word doesn't outrank a short one that defines it. An exact
phrase match adds a bonus on top. This won't find conceptually related text
that doesn't share words with the query (e.g. a query for "revenue" won't
match a chunk that only says "income"). A
semantic mode is real future scope, gated the same way `ConvertConfig.use_llm`
already gates another capability that needs a real provider key to build and
test against - not something to fake with an untested embedding call.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

from docmd.converters.base import Chunk

_WORD_RE = re.compile(r"\w+")
_EXACT_PHRASE_BONUS = 3.0
# Standard BM25 defaults: k1 controls how fast repeated occurrences of a term
# saturate, b how strongly chunk length is normalized against the average.
_BM25_K1 = 1.5
_BM25_B = 0.75


@dataclass
class SearchResult:
    source: str
    """Path of the chunk file this result came from, relative to the
    directory `search()` was called with."""
    chunk: Chunk
    score: float


def _tokenize(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def _bm25(
    query_words: list[str],
    query_phrase: str,
    text: str,
    doc_freq: dict[str, int],
    total_chunks: int,
    avg_length: float,
) -> float:
    words = _tokenize(text)
    length = len(words) or 1
    score = 0.0
    for word in query_words:
        term_freq = words.count(word)
        if not term_freq:
            continue
        idf = math.log(1 + (total_chunks - doc_freq[word] + 0.5) / (doc_freq[word] + 0.5))
        norm = term_freq + _BM25_K1 * (1 - _BM25_B + _BM25_B * length / avg_length)
        score += idf * term_freq * (_BM25_K1 + 1) / norm
    if score and query_phrase in text.lower():
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
    ranked by BM25 relevance, highest first."""
    query_words = list(dict.fromkeys(_tokenize(query)))
    if not query_words:
        return []
    query_phrase = query.lower()

    loaded: list[tuple[str, Chunk]] = []
    for json_path in sorted(directory.rglob("*.json")):
        try:
            chunks = _load_chunks(json_path)
        except (json.JSONDecodeError, TypeError, KeyError):
            # Not a chunk file docmd produced (or produced by a version with
            # a different shape) - skip it rather than crashing the whole
            # search over one unrelated or stale file.
            continue
        source = str(json_path.relative_to(directory))
        loaded.extend((source, chunk) for chunk in chunks)

    if not loaded:
        return []

    # BM25 needs corpus-wide statistics, so every chunk is tokenized once up
    # front for document frequency and average length.
    doc_freq = dict.fromkeys(query_words, 0)
    total_words = 0
    for _, chunk in loaded:
        words = _tokenize(chunk.text)
        total_words += len(words)
        present = set(words)
        for word in query_words:
            if word in present:
                doc_freq[word] += 1
    avg_length = max(total_words / len(loaded), 1.0)

    results: list[SearchResult] = []
    for source, chunk in loaded:
        score = _bm25(query_words, query_phrase, chunk.text, doc_freq, len(loaded), avg_length)
        if score > 0:
            results.append(SearchResult(source=source, chunk=chunk, score=score))

    results.sort(key=lambda r: r.score, reverse=True)
    return results[:limit]
