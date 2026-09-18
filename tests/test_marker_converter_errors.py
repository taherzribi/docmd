"""Unit tests for MarkerConverter's exception classification - mocked so
these run fast and don't depend on whether llama-server happens to be
installed on the machine running the tests. See
docmd/converters/marker_converter.py for the real (slow, environment-
dependent) version of this failure, found via real OCR testing on a
genuinely scanned PDF from archive.org.
"""

from __future__ import annotations

import docmd.converters.marker_converter as marker_converter_module
from docmd.config import ConvertConfig
from docmd.converters.marker_converter import MarkerConverter
from docmd.errors import MissingSystemDependencyError


class _FakeSpawnError(Exception):
    """Stands in for surya.inference.backends.spawn.SpawnError without
    importing surya's internal exception class directly."""


class _FakePdfConverterMissingBinary:
    def __init__(self, **_kwargs) -> None:
        pass

    def __call__(self, _filepath: str):
        raise _FakeSpawnError(
            "llama-server binary not found. Install with:\n"
            "  macOS:  brew install llama.cpp"
        )


def test_missing_llama_server_binary_raises_clear_error(monkeypatch, tmp_path):
    monkeypatch.setattr(marker_converter_module, "_get_model_dict", lambda: {})
    monkeypatch.setattr(
        "marker.converters.pdf.PdfConverter", _FakePdfConverterMissingBinary
    )

    dummy_pdf = tmp_path / "dummy.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4\n%%EOF")

    try:
        MarkerConverter().convert(str(dummy_pdf), ConvertConfig())
        raise AssertionError("expected MissingSystemDependencyError")
    except MissingSystemDependencyError as exc:
        message = str(exc)
        assert "llama.cpp" in message
        assert "brew install llama.cpp" in message
        assert "LLAMA_CPP_BINARY" in message
