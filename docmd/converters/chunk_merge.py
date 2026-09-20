"""Merges adjacent raw block-level chunks up to a token budget - see
`ConvertConfig.chunk_max_tokens`.

A pure function over `list[Chunk]`, independent of any backend: this runs
after `chunk_extraction.py` has already produced one chunk per block, so it
doesn't need Marker's block tree at all.
"""

from __future__ import annotations

from docmd.converters.base import Chunk

# Content types that can be merged into a bigger chunk. Tables, images, and
# lists stay atomic - flattening a table's cell text into surrounding prose
# loses its structure, and an image chunk's empty text has nothing to merge.
_MERGEABLE_TYPES = {"text", "heading"}


def _estimate_tokens(text: str) -> int:
    """~4 characters/token is a common rough estimate for English text -
    not a real tokenizer, since the exact count varies by embedding model
    anyway and pulling in one just for an estimate isn't worth the
    dependency weight."""
    return max(1, len(text) // 4)


def merge_chunks(chunks: list[Chunk], max_tokens: int) -> list[Chunk]:
    """Merges consecutive mergeable chunks (same page, same section) up to
    `max_tokens`. A single chunk already at or over the budget is left as
    its own group rather than split - splitting an oversized block is a
    separate, harder problem this doesn't attempt."""
    merged: list[Chunk] = []
    buffer: list[Chunk] = []
    buffer_tokens = 0

    def flush() -> None:
        nonlocal buffer_tokens
        if not buffer:
            return
        if len(buffer) == 1:
            merged.append(buffer[0])
        else:
            merged.append(
                Chunk(
                    text="\n\n".join(c.text for c in buffer),
                    page=buffer[0].page,
                    section=buffer[0].section,
                    content_type="text",
                    bbox=(
                        min(c.bbox[0] for c in buffer),
                        min(c.bbox[1] for c in buffer),
                        max(c.bbox[2] for c in buffer),
                        max(c.bbox[3] for c in buffer),
                    ),
                )
            )
        buffer.clear()
        buffer_tokens = 0

    for chunk in chunks:
        if chunk.content_type not in _MERGEABLE_TYPES:
            flush()
            merged.append(chunk)
            continue

        chunk_tokens = _estimate_tokens(chunk.text)
        continues_buffer = buffer and buffer[-1].page == chunk.page and buffer[-1].section == chunk.section

        if buffer and (not continues_buffer or buffer_tokens + chunk_tokens > max_tokens):
            flush()

        buffer.append(chunk)
        buffer_tokens += chunk_tokens

    flush()
    return merged
