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


class Converter(Protocol):
    """A document -> Markdown conversion engine."""

    def convert(self, filepath: str | Path, config: ConvertConfig) -> ConversionResult:
        """Convert the file at `filepath` into a ConversionResult."""
        ...
