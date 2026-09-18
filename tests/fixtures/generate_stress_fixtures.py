"""Regenerates the stress-test PDF fixtures used to prove post-processing
fixes real Marker defects, not just hand-crafted markdown strings. See
tests/test_postprocess_integration.py for stress.pdf, and
tests/test_postprocess_more_integration.py for the ones generated here.

    python tests/fixtures/generate_stress_fixtures.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

FIXTURES_DIR = Path(__file__).parent
styles = getSampleStyleSheet()
body = styles["BodyText"]
h_title = ParagraphStyle("H0", fontSize=28, leading=32, fontName="Helvetica-Bold")
h_big = ParagraphStyle("H1", fontSize=22, leading=26, fontName="Helvetica-Bold")


def generate_running_header() -> None:
    """4-page document with a bold header drawn at a fixed position on every
    page (not a flowable heading) - tests whether that gets misdetected as a
    duplicate heading, and whether structurally identical section headings
    get assigned consistent levels throughout."""

    def draw_header(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica-Bold", 14)
        canvas.drawString(72, 740, "CONFIDENTIAL - INTERNAL REPORT")
        canvas.restoreState()

    doc = SimpleDocTemplate(str(FIXTURES_DIR / "running_header.pdf"), pagesize=LETTER)
    story = [Paragraph("Quarterly Risk Review", h_title), Spacer(1, 20)]
    for section in range(1, 5):
        story.append(Paragraph(f"Section {section}: Findings", h_big))
        story.append(
            Paragraph(
                (f"This is body paragraph content for section {section}. ") * 20,
                body,
            )
        )
        story.append(PageBreak())
    doc.build(story, onFirstPage=draw_header, onLaterPages=draw_header)


def generate_merged_cells() -> None:
    """A table with a spanned header cell (merged columns) - tests whether
    that breaks raw column-count reconstruction."""
    rows = [
        ["", "Q1 2026", "", "Q2 2026", ""],
        ["Region", "Revenue", "Growth", "Revenue", "Growth"],
        ["West", "$1.2M", "+5%", "$1.4M", "+17%"],
        ["East", "$0.9M", "+2%", "$1.0M", "+11%"],
    ]
    doc = SimpleDocTemplate(str(FIXTURES_DIR / "merged_cells.pdf"), pagesize=LETTER)
    table = Table(
        rows,
        style=TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("SPAN", (1, 0), (2, 0)),
                ("SPAN", (3, 0), (4, 0)),
                ("BACKGROUND", (0, 0), (-1, 1), colors.lightgrey),
            ]
        ),
    )
    doc.build([Paragraph("Regional Revenue", h_big), Spacer(1, 10), table])


def generate_with_image() -> None:
    """A PDF with a real embedded image, to test image_handling.py against
    real Marker image extraction rather than a synthetic dict."""
    img_path = FIXTURES_DIR / "_gen_chart.png"
    PILImage.new("RGB", (300, 200), color=(70, 130, 180)).save(img_path)

    doc = SimpleDocTemplate(str(FIXTURES_DIR / "with_image.pdf"), pagesize=LETTER)
    doc.build(
        [
            Paragraph("Revenue Chart", h_big),
            Spacer(1, 10),
            Paragraph("See the chart below for regional performance.", body),
            Spacer(1, 10),
            Image(str(img_path), width=3 * inch, height=2 * inch),
            Spacer(1, 10),
            Paragraph("Chart data is preliminary and subject to revision.", body),
        ]
    )
    img_path.unlink()  # embedded in the PDF now, don't need the source file


if __name__ == "__main__":
    generate_running_header()
    generate_merged_cells()
    generate_with_image()
    print(f"wrote stress fixtures to {FIXTURES_DIR}")
