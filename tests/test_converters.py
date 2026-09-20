"""Integration tests that run real conversions through Marker.

First run downloads Marker/Surya's model weights (a few hundred MB to ~1GB)
and is slow; subsequent runs reuse the local Hugging Face cache.
"""

import ctypes.util
from pathlib import Path

import pytest

from docmd import convert_document
from docmd.errors import UnsupportedFormatError

FIXTURES = Path(__file__).parent / "fixtures"

# DOCX/PPTX go through weasyprint, which needs native Pango/GObject/Cairo
# libraries that pip cannot install - a system package manager (apt, brew)
# has to provide them. CI installs them explicitly (see .github/workflows/ci.yml);
# a local dev machine without them (e.g. no Homebrew yet) skips this test
# rather than failing on an environment gap that isn't a docmd bug.
_HAS_WEASYPRINT_DEPS = ctypes.util.find_library("gobject-2.0") is not None


def test_convert_pdf_produces_structured_markdown():
    result = convert_document(str(FIXTURES / "sample.pdf"))
    assert result.page_count == 1
    first_line = result.markdown.splitlines()[0]
    assert first_line.startswith("# ") and "Q3 Regional Sales Report" in first_line
    assert "Executive Summary" in result.markdown
    assert "Region" in result.markdown and "Revenue" in result.markdown
    assert "|" in result.markdown  # a table survived


def test_convert_document_includes_provenance():
    """docmd's own tracking info (docmd_version, backend, backend_version,
    ocr_used, conversion_duration_ms), same shape regardless of which
    backend ran - see docmd/converters/base.py:ConversionResult.provenance.
    For debugging "this converted differently yesterday"."""
    result = convert_document(str(FIXTURES / "sample.pdf"))
    prov = result.provenance
    assert prov["backend"] == "marker"
    assert prov["docmd_version"] != "unknown"
    assert prov["backend_version"] != "unknown"
    assert prov["ocr_used"] is False  # sample.pdf has a real text layer
    assert isinstance(prov["conversion_duration_ms"], int)
    assert prov["conversion_duration_ms"] > 0


@pytest.mark.skipif(
    not _HAS_WEASYPRINT_DEPS,
    reason="weasyprint's native deps (Pango/GObject/Cairo) aren't installed "
    "on this machine - e.g. run `brew install pango` on macOS, or see "
    "https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation",
)
def test_convert_docx_produces_structured_markdown():
    result = convert_document(str(FIXTURES / "sample.docx"))
    assert "Q3 Regional Sales Report" in result.markdown
    assert "Executive Summary" in result.markdown
    assert "Region" in result.markdown


def test_convert_unsupported_format_raises():
    with pytest.raises(UnsupportedFormatError):
        convert_document(str(FIXTURES / "generate_fixtures.py"))


@pytest.mark.skipif(
    not _HAS_WEASYPRINT_DEPS,
    reason="weasyprint's native deps (Pango/GObject/Cairo) aren't installed on this machine",
)
def test_convert_pptx_gives_each_slide_its_own_section():
    """Found via real decks (Apache POI's public test set): Marker's PPTX
    provider flows all slides into one document paginated by content height,
    so 34 slides became 15 "pages" and nothing marked where a slide started.
    Its own `include_slide_number` option can't be enabled through config in
    marker-pdf 2.0.0 (see marker_converter._enable_slide_headings)."""
    result = convert_document(str(FIXTURES / "sample.pptx"))
    for n in (1, 2, 3):
        assert f"Slide {n}" in result.markdown
    assert result.markdown.index("Slide 1") < result.markdown.index("Slide 2") < result.markdown.index("Slide 3")


@pytest.mark.skipif(
    not _HAS_WEASYPRINT_DEPS,
    reason="weasyprint's native deps (Pango/GObject/Cairo) aren't installed on this machine",
)
def test_pptx_chunk_sections_name_their_slide():
    from docmd.config import ConvertConfig

    result = convert_document(str(FIXTURES / "sample.pptx"), config=ConvertConfig(include_chunks=True))
    slide_roots = {c.section.split(" > ")[0] for c in result.chunks if c.section.startswith("Slide")}
    assert slide_roots == {"Slide 1", "Slide 2", "Slide 3"}
    titled = [c for c in result.chunks if c.section == "Slide 2 > Customer Retention"]
    assert titled, "slide title should nest under its slide heading"
