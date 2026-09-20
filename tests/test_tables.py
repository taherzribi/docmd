"""Tests for docmd/tables.py (docmd extract --tables csv)."""

from __future__ import annotations

from docmd.tables import extract_tables_as_csv


def test_extracts_a_single_table_as_csv():
    md = "| A | B |\n| --- | --- |\n| 1 | 2 |\n| 3 | 4 |\n"
    tables = extract_tables_as_csv(md)
    assert len(tables) == 1
    assert tables[0] == "A,B\r\n1,2\r\n3,4\r\n"


def test_extracts_multiple_tables_in_document_order():
    md = (
        "Some prose.\n\n"
        "| A | B |\n| --- | --- |\n| 1 | 2 |\n\n"
        "More prose.\n\n"
        "| X | Y |\n| --- | --- |\n| 9 | 8 |\n"
    )
    tables = extract_tables_as_csv(md)
    assert len(tables) == 2
    assert tables[0].startswith("A,B")
    assert tables[1].startswith("X,Y")


def test_returns_empty_list_when_no_tables():
    assert extract_tables_as_csv("Just some prose, no tables here.\n") == []


def test_unescapes_markdown_backslash_escapes():
    """Real Marker output found via a real Berkshire Hathaway filing table:
    a dollar figure renders in Markdown as `\\$ 5,428` (correct, so a
    Markdown/KaTeX renderer doesn't read `$` as a math delimiter) - that
    escaping is meaningless once re-purposed as CSV, so it's undone here."""
    md = "| Segment | Amount |\n| --- | --- |\n| Insurance | \\$ 5,428 |\n"
    tables = extract_tables_as_csv(md)
    assert "\\$" not in tables[0]
    assert "$ 5,428" in tables[0]


def test_values_with_commas_are_properly_csv_quoted():
    md = "| Year | Value |\n| --- | --- |\n| 2023 | 4,384,748 |\n"
    tables = extract_tables_as_csv(md)
    assert '"4,384,748"' in tables[0]
