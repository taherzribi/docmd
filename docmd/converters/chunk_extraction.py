"""Extracts `Chunk` objects from Marker's raw block tree, before it gets
flattened into a single Markdown string.

Only usable with Marker's pre-render `Document` object (see
`PdfConverter.build_document()`), which is why this lives next to
`marker_converter.py` rather than in `docmd/postprocess/` - it needs the
backend's actual block/page/geometry structure, not a Markdown string.
"""

from __future__ import annotations

from typing import Any

from docmd.converters.base import Chunk
from docmd.heading_numbering import NumberingLevels

# A font size at or below this is a PDF scaling artifact, not a real size:
# found on a real RFC, SEC-style letter and court opinion, all of which report
# 1.0 for every span (the text matrix does the actual scaling), so it says
# nothing about a heading's visual rank.
_MIN_REAL_FONT_SIZE = 2.0
# Headings within this fraction of each other's font size are one style.
# Same-style headings measure a few percent apart from rounding and
# hinting; genuinely different ranks are usually 15%+ apart.
_SIZE_TOLERANCE = 0.94


# Marker has dozens of internal block types; this maps the ones that carry
# real chunk-worthy text onto docmd's small, stable, backend-agnostic
# vocabulary (see Chunk.content_type). Anything not listed here falls back
# to "text" - a safe default for content that's still real prose, just an
# internal type this mapping doesn't know about yet.
_CONTENT_TYPE_MAP = {
    "SectionHeader": "heading",
    "Table": "table",
    "Form": "table",
    "TableOfContents": "table",
    "ListGroup": "list",
    "ListItem": "list",
    "Picture": "image",
    "Figure": "image",
    "PictureGroup": "image",
    "FigureGroup": "image",
}

# Image blocks have no text of their own (raw_text() is always empty) - they
# still get a chunk, carrying page/section/bbox with an empty text field,
# rather than being silently dropped by the "no text, skip it" rule that
# correctly filters out genuinely empty text/table blocks.
_IMAGE_BLOCK_TYPES = {"Picture", "Figure", "PictureGroup", "FigureGroup"}


def _heading_font_size(block: Any, document: Any) -> float | None:
    """The first span's font size, or None if unavailable or not a real
    size (see _MIN_REAL_FONT_SIZE)."""
    contained = getattr(block, "contained_blocks", None)
    if contained is None:
        return None
    for span in contained(document):
        if span.block_type.name == "Span":
            size = getattr(span, "font_size", None)
            return size if size and size > _MIN_REAL_FONT_SIZE else None
    return None


def _size_ranks(sizes: list[float]) -> list[float]:
    """Representative size for each distinct heading style, largest first."""
    reps: list[float] = []
    for size in sorted(set(sizes), reverse=True):
        if not reps or size < reps[-1] * _SIZE_TOLERANCE:
            reps.append(size)
    return reps


def _rank_of(size: float, reps: list[float]) -> int:
    for index, rep in enumerate(reps, start=1):
        if size >= rep * _SIZE_TOLERANCE:
            return index
    return len(reps)


def extract_chunks(document: Any) -> list[Chunk]:
    """Walks every page's top-level blocks in document order, building one
    Chunk per block that has real text and isn't flagged by Marker itself as
    excluded from output (`ignore_for_output` - the same flag that already
    correctly suppresses a repeated running header misclassified as a
    heading on later pages, independent of docmd's own heading_normalize.py,
    which guards against the same defect at the Markdown-string level for
    everything ignore_for_output doesn't catch)."""
    chunks: list[Chunk] = []
    heading_stack: dict[int, str] = {}
    last_level = 0
    numbering = NumberingLevels()

    # Marker's heading_level is visually inferred and noisy: on a real
    # 961-page book every chapter heading is the same 14pt, yet Marker gave
    # them four different levels. Where a PDF reports real font sizes,
    # headings of the same size are the same level - ranked by size, largest
    # shallowest - and Marker's own level is only the fallback for PDFs that
    # don't (sizes of 1.0), where nothing better is available.
    sizes: dict[str, float] = {}
    for page in document.pages:
        for block_id in page.structure or []:
            block = document.get_block(block_id)
            if block.block_type.name == "SectionHeader" and not getattr(block, "ignore_for_output", False):
                size = _heading_font_size(block, document)
                if size is not None:
                    sizes[block_id] = size
    reps = _size_ranks(list(sizes.values()))

    for page in document.pages:
        for block_id in page.structure or []:
            block = document.get_block(block_id)

            if getattr(block, "ignore_for_output", False):
                continue

            text = (block.raw_text(document) or "").strip()
            block_type_name = block.block_type.name

            heading_level = getattr(block, "heading_level", None)
            if block_type_name == "SectionHeader" and heading_level:
                # A real size ranking is used as-is, not clamped: a document
                # may legitimately jump from its largest heading to its
                # smallest, and level gaps are harmless in a breadcrumb,
                # whereas clamping staircases same-size headings into
                # ever-deeper levels (found on a real DOCX news digest, where
                # each city heading nested under the article title before it).
                # With no size signal, Marker's own noisy level is limited to
                # deepening by at most one relative to the last heading, the
                # same rule heading_normalize.py applies to Markdown.
                hint = (
                    _rank_of(sizes[block_id], reps)
                    if block_id in sizes
                    else min(heading_level, last_level + 1)
                )
                # A visible section number outranks both: its structure
                # relative to other numbered headings is unambiguous.
                resolved = numbering.resolve(text, hint)
                heading_level = resolved if resolved is not None else hint
                for level in [lvl for lvl in heading_stack if lvl >= heading_level]:
                    del heading_stack[level]
                if text:
                    # A heading wrapped across lines in the PDF ("GOLDEY, ...
                    # v. FIELDS \net al.") keeps its raw line breaks in the
                    # block's text - collapsed so the breadcrumb is one line.
                    heading_stack[heading_level] = " ".join(text.split())
                last_level = heading_level

            if not text and block_type_name not in _IMAGE_BLOCK_TYPES:
                continue

            polygon = getattr(block, "polygon", None)
            bbox = tuple(polygon.bbox) if polygon is not None else (0.0, 0.0, 0.0, 0.0)
            section = " > ".join(heading_stack[level] for level in sorted(heading_stack))

            chunks.append(
                Chunk(
                    text=text,
                    page=block.page_id if block.page_id is not None else page.page_id,
                    section=section,
                    content_type=_CONTENT_TYPE_MAP.get(block_type_name, "text"),
                    bbox=bbox,
                )
            )

    return chunks
