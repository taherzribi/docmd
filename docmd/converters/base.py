"""Converter interface.

Every converter (currently just Marker; the registry exists so a second
engine could be added later without touching callers) implements this
protocol: take a filepath, return a ConversionResult.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from docmd.config import ConvertConfig

# The stable, backend-agnostic vocabulary for Chunk.content_type. Deliberately
# small and independent of any one backend's internal block-type taxonomy
# (Marker alone has dozens) - see docmd/converters/marker_converter.py for the
# mapping from Marker's own types onto this set.
CONTENT_TYPES = frozenset({"text", "heading", "table", "image", "list"})


@dataclass
class Chunk:
    """One retrieval-sized unit of a converted document, for RAG/search use
    cases that need more than a single Markdown string - see
    `ConvertConfig.include_chunks`.

    One chunk per structural block the backend identified (a paragraph, a
    table, a heading, ...), not a token-budgeted or semantically merged
    chunk - that's real future scope, not what this ships today.

    `text` is the block's own raw text, extracted before docmd's Markdown
    post-processing pipeline runs - it does not get table_cleanup's,
    heading_normalize's, or rtl_fix's fixes, since those operate on the
    final rendered Markdown *string*, not on individual blocks. A table
    chunk's text is Marker's own flattened cell text, not a clean Markdown
    table.
    """

    text: str
    page: int
    """0-indexed page number the block appeared on."""
    section: str
    """Breadcrumb of the nearest heading at each level above this block,
    joined with " > " (e.g. "Chapter 3 > 3.1 Introduction"), so a chunk
    under a deeply nested heading doesn't lose its ancestor context. Empty
    string if the chunk precedes any heading in the document."""
    content_type: str
    """One of CONTENT_TYPES - never a raw backend-specific block-type name."""
    bbox: tuple[float, float, float, float]
    """(x0, y0, x1, y1) in the backend's native coordinate space - not
    normalized to a 0-1 range, and not guaranteed comparable across
    backends. Good for "where on the page was this" within one document."""


@dataclass
class ConversionResult:
    """The raw result of running a document through a conversion engine,
    before docmd's own post-processing pass runs on top of it.
    """

    markdown: str
    page_count: int
    images: dict[str, Any] = field(default_factory=dict)
    """Maps an image filename referenced in `markdown` (e.g.
    '_page_0_Figure_1.jpeg') to a PIL.Image.Image instance."""
    metadata: dict[str, Any] = field(default_factory=dict)
    """Whatever the backend itself returned - opaque, backend-specific, not
    a contract. For Marker this is its own metadata dict (page_stats,
    table_of_contents, ...). A different backend would put different keys
    here; don't build stable behavior on top of this dict's shape."""
    provenance: dict[str, Any] = field(default_factory=dict)
    """docmd's own tracking info, same shape regardless of which backend
    ran: docmd_version, backend, backend_version, ocr_used,
    conversion_duration_ms. For debugging "this converted differently
    yesterday" - see ARCHITECTURE.md."""
    chunks: list[Chunk] | None = None
    """Populated only when `ConvertConfig.include_chunks` is set - None
    (not an empty list) means "not requested", so callers can tell that
    apart from "requested, but the document had no content"."""


class Converter(Protocol):
    """A document -> Markdown conversion engine."""

    def convert(self, filepath: str | Path, config: ConvertConfig) -> ConversionResult:
        """Convert the file at `filepath` into a ConversionResult."""
        ...
