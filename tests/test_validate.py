"""Tests for docmd/validate.py (docmd validate). See test_benchmark.py for
the same checks run against the whole real-document fixture corpus."""

from __future__ import annotations

from docmd.validate import validate_markdown


def test_clean_document_has_no_warnings():
    md = "# Title\n\nSome text.\n\n## Section\n\nMore text.\n"
    report = validate_markdown(md)
    assert not report.has_warnings
    assert any("heading" in f.message and f.ok for f in report.findings)


def test_heading_level_skip_is_a_warning():
    md = "# Title\n\n#### Way too deep\n"
    report = validate_markdown(md)
    assert report.has_warnings
    assert any("level skip" in f.message for f in report.findings if not f.ok)


def test_orphaned_empty_heading_is_a_warning():
    md = "# Title\n\n#\n\nSome text.\n"
    report = validate_markdown(md)
    assert any("orphaned empty heading" in f.message for f in report.findings if not f.ok)


def test_duplicate_adjacent_heading_is_a_warning():
    md = "# Title\n\n## Repeat\n\n## Repeat\n\nText.\n"
    report = validate_markdown(md)
    assert any("duplicated heading" in f.message for f in report.findings if not f.ok)


def test_inconsistent_table_columns_is_a_warning():
    md = "| A | B |\n| --- | --- |\n| 1 | 2 | 3 |\n"
    report = validate_markdown(md)
    assert any("inconsistent column" in f.message for f in report.findings if not f.ok)


def test_consistent_table_is_ok():
    md = "| A | B |\n| --- | --- |\n| 1 | 2 |\n| 3 | 4 |\n"
    report = validate_markdown(md)
    assert not report.has_warnings
    assert any("table" in f.message and f.ok for f in report.findings)


def test_malformed_empty_image_reference_is_a_warning():
    md = "Some text.\n\n![]()\n"
    report = validate_markdown(md)
    assert any("malformed" in f.message for f in report.findings if not f.ok)


def test_document_with_no_tables_reports_no_table_finding():
    md = "# Title\n\nJust prose, no tables.\n"
    report = validate_markdown(md)
    assert not any("table" in f.message for f in report.findings)
