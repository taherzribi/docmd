"""Integration test proving post-processing fixes a *real* Marker bug, not
just hand-crafted markdown strings (see tests/test_postprocess.py for those -
useful for fast unit coverage, but circular as evidence of real-world value,
since the input was written to match what the regex expects).

fixtures/stress.pdf has a 45-row table that spans a PDF page break
(reportlab's repeatRows=1, matching how real multi-page business reports are
laid out). Marker processes pages independently, so it renders this as two
separate Markdown tables with a duplicated header row in between - this test
converts the real PDF through real Marker, confirms that split actually
happens (so this test fails loudly if a future Marker version stops doing
it, rather than silently testing nothing), then confirms docmd's full
convert() pipeline merges them back into one continuous table.
"""

from pathlib import Path

from docmd import convert_document
from docmd.config import ConvertConfig
from docmd.converters.marker_converter import MarkerConverter

FIXTURE = Path(__file__).parent / "fixtures" / "stress.pdf"


def test_marker_really_does_split_a_page_spanning_table():
    """Documents the real upstream behavior this feature exists to fix."""
    raw = MarkerConverter().convert(str(FIXTURE), ConvertConfig())
    # Raw Marker output pads cell widths with extra spaces for column
    # alignment (e.g. "| Region  | Rep    |"), so match loosely rather than
    # on an exact literal string.
    header_count = sum(
        1
        for line in raw.markdown.splitlines()
        if "Region" in line and "Revenue" in line and line.strip().startswith("|")
    )
    assert header_count >= 2, (
        "expected Marker to render the page-spanning table as 2+ blocks "
        "with a repeated header - if this fails, Marker's behavior changed "
        "and test_docmd_merges_the_split_table's premise needs revisiting"
    )


def test_docmd_merges_the_split_table():
    result = convert_document(str(FIXTURE))
    markdown = result.markdown

    # One continuous table: header appears exactly once, not once per page.
    assert markdown.count("| Region | Rep | Deal | Revenue | Status |") == 1

    # All 45 data rows survived the merge - none silently dropped, including
    # the ones on both sides of where the original page-break duplicate
    # header used to sit (rows 27 and 28 of 45).
    for i in range(1, 46):
        assert f"Deal-{1000 + i}" in markdown

    # The row right after the original page-break duplicate header is still
    # present as a *data* row, not swallowed along with the header.
    assert "North | Rep 28 | Deal-1028" in markdown


def test_docmd_promotes_first_heading_to_h1():
    """Source PDF's title paragraph rendered as H2 in raw Marker output (its
    font size wasn't visually distinct enough for Marker's heading-level
    detection) - docmd promotes a document's opening heading to H1 rather
    than leaving it start at H2 with no root."""
    result = convert_document(str(FIXTURE))
    first_line = result.markdown.splitlines()[0]
    assert first_line.startswith("# ") and "Annual Sales Report" in first_line
