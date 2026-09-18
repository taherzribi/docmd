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


class Converter(Protocol):
    """A document -> Markdown conversion engine."""

    def convert(self, filepath: str | Path, config: ConvertConfig) -> ConversionResult:
        """Convert the file at `filepath` into a ConversionResult."""
        ...
