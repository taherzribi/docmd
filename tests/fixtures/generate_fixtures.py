"""Regenerates the sample PDF/DOCX fixtures used by the tests.

Not run automatically - the generated files are committed to the repo so
tests don't need reportlab/python-docx installed to run. Re-run this after
changing the fixture content:

    python tests/fixtures/generate_fixtures.py
"""

from __future__ import annotations

from pathlib import Path

FIXTURES_DIR = Path(__file__).parent

TABLE_ROWS = [
    ("Region", "Revenue", "Growth"),
    ("West", "$2.1M", "+18%"),
    ("East", "$1.8M", "+9%"),
    ("South", "$1.2M", "+4%"),
]


def generate_pdf() -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import (
        ListFlowable,
        ListItem,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(FIXTURES_DIR / "sample.pdf"), pagesize=LETTER)
    story = [
        Paragraph("Q3 Regional Sales Report", styles["Title"]),
        Spacer(1, 12),
        Paragraph("Executive Summary", styles["Heading1"]),
        Paragraph(
            "Revenue grew 14% quarter-over-quarter, driven primarily by strong "
            "performance in the West region.",
            styles["BodyText"],
        ),
        Spacer(1, 12),
        Paragraph("Regional Breakdown", styles["Heading1"]),
        Table(
            TABLE_ROWS,
            style=TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ]
            ),
        ),
        Spacer(1, 12),
        Paragraph("Key Takeaways", styles["Heading1"]),
        ListFlowable(
            [
                ListItem(Paragraph("Enterprise deals closed 22% faster than Q2", styles["BodyText"])),
                ListItem(Paragraph("Churn held steady at 3.1%", styles["BodyText"])),
            ],
            bulletType="bullet",
        ),
    ]
    doc.build(story)


def generate_docx() -> None:
    from docx import Document

    doc = Document()
    doc.add_heading("Q3 Regional Sales Report", level=1)
    doc.add_heading("Executive Summary", level=2)
    doc.add_paragraph(
        "Revenue grew 14% quarter-over-quarter, driven primarily by strong "
        "performance in the West region."
    )
    doc.add_heading("Regional Breakdown", level=2)
    table = doc.add_table(rows=1, cols=3)
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    hdr[0].text, hdr[1].text, hdr[2].text = TABLE_ROWS[0]
    for region, revenue, growth in TABLE_ROWS[1:]:
        row = table.add_row().cells
        row[0].text, row[1].text, row[2].text = region, revenue, growth
    doc.add_heading("Key Takeaways", level=2)
    doc.add_paragraph("Enterprise deals closed 22% faster than Q2", style="List Bullet")
    doc.add_paragraph("Churn held steady at 3.1%", style="List Bullet")
    doc.save(str(FIXTURES_DIR / "sample.docx"))


if __name__ == "__main__":
    generate_pdf()
    generate_docx()
    print(f"wrote fixtures to {FIXTURES_DIR}")
