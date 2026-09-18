"""Maps a file extension to the converter (and required extras) that handle it.

Kept as a registry rather than hardcoding checks in the CLI/library entrypoint
so a second conversion engine could be added later without touching callers.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from docmd.converters.base import Converter
from docmd.converters.marker_converter import MarkerConverter
from docmd.errors import MissingExtraError, UnsupportedFormatError

# suffix -> module that must be importable for that format to work.
# None means "supported by the base install, no extra needed".
_SUPPORTED_SUFFIXES: dict[str, str | None] = {
    ".pdf": None,
    ".docx": "mammoth",
    ".pptx": "pptx",
}

_marker_converter = MarkerConverter()


def get_converter(filepath: str | Path) -> Converter:
    """Return the Converter that should handle `filepath`.

    Raises:
        UnsupportedFormatError: the extension isn't one docmd knows about.
        MissingExtraError: the extension needs `pip install docmd[full]`.
    """
    suffix = Path(filepath).suffix.lower()

    if suffix not in _SUPPORTED_SUFFIXES:
        raise UnsupportedFormatError(suffix)

    required_module = _SUPPORTED_SUFFIXES[suffix]
    if required_module and importlib.util.find_spec(required_module) is None:
        raise MissingExtraError(suffix)

    return _marker_converter
