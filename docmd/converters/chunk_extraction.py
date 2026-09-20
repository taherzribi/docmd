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

    for page in document.pages:
        for block_id in page.structure or []:
            block = document.get_block(block_id)

            if getattr(block, "ignore_for_output", False):
                continue

            text = (block.raw_text(document) or "").strip()
            block_type_name = block.block_type.name

            heading_level = getattr(block, "heading_level", None)
            if block_type_name == "SectionHeader" and heading_level:
                for level in [lvl for lvl in heading_stack if lvl >= heading_level]:
                    del heading_stack[level]
                if text:
                    heading_stack[heading_level] = text

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
