"""Extracts `Chunk` objects from Marker's raw block tree, before it gets
flattened into a single Markdown string.

Only usable with Marker's pre-render `Document` object (see
`PdfConverter.build_document()`), which is why this lives next to
`marker_converter.py` rather than in `docmd/postprocess/` - it needs the
backend's actual block/page/geometry structure, not a Markdown string.
"""

from __future__ import annotations

import re
from typing import Any

from docmd.converters.base import Chunk

# A heading's own visible numbering ("5.4", "5.4.1") is unambiguous ground
# truth for its nesting depth - unlike Marker's visually-inferred
# heading_level, which can assign a *reachable* but wrong absolute level
# (found via a real RFC: "5.4 Error Handling" got the same level as the
# deeper "5.3.1"/"5.3.2" before it, nesting it under sibling "5.3" instead of
# next to it - a defect the simple "don't skip more than one level deeper"
# clamp below doesn't catch, since 5.4's level wasn't a *skip*, just wrong).
# Requires at least one embedded dot (two-plus segments) so a heading that
# merely starts with a bare number ("2024 Outlook") - too ambiguous a signal
# for nesting depth - never triggers this override.
_NUMBERING_RE = re.compile(r"^(\d+(?:\.\d+)+)\.?\s")


def _numbering_depth(text: str) -> int | None:
    match = _NUMBERING_RE.match(text)
    return match.group(1).count(".") + 1 if match else None


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

    for page in document.pages:
        for block_id in page.structure or []:
            block = document.get_block(block_id)

            if getattr(block, "ignore_for_output", False):
                continue

            text = (block.raw_text(document) or "").strip()
            block_type_name = block.block_type.name

            heading_level = getattr(block, "heading_level", None)
            if block_type_name == "SectionHeader" and heading_level:
                numbering_depth = _numbering_depth(text)
                if numbering_depth is not None:
                    heading_level = numbering_depth
                elif heading_level > last_level + 1:
                    # No numbering to trust instead - fall back to clamping
                    # a sudden jump, the same rule heading_normalize.py
                    # applies for Markdown output: a level may deepen by at
                    # most one relative to the last heading actually used.
                    heading_level = last_level + 1
                for level in [lvl for lvl in heading_stack if lvl >= heading_level]:
                    del heading_stack[level]
                if text:
                    heading_stack[heading_level] = text
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
