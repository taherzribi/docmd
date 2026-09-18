"""The docmd contract benchmark: runs every CONTRACT.md guarantee against
the *whole* fixture corpus in one place, as a scorecard rather than each
guarantee being checked only against the one fixture that first found its
bug (scattered across test_postprocess.py, test_postprocess_integration.py,
and test_postprocess_more_integration.py).

This is deliberately not a numeric/percentage benchmark. CONTRACT.md's
guarantees are pass/fail by design - see its own "Writing a new test
against this contract" section - and a percentage score across documents
would hide exactly the kind of regression this file exists to catch: one
fixture silently breaking a guarantee that still holds everywhere else.

The other test files remain the source of truth for *why* each guarantee
exists (the real bug it fixes, with the document it was found on). This
file exists so a future change - a Marker version bump, a dependency
upgrade, a refactor - gets checked against every fixture, not just the
original one.
"""

from __future__ import annotations

import ctypes.util
import re
from pathlib import Path

import pytest

from docmd import convert_document

FIXTURES = Path(__file__).parent / "fixtures"

# sample.docx goes through weasyprint, which needs native Pango/GObject/Cairo
# libraries pip can't install - see tests/test_converters.py for the same
# check. Excluded from the corpus rather than failing on an environment gap
# that isn't a docmd bug; CI has these libraries installed.
_HAS_WEASYPRINT_DEPS = ctypes.util.find_library("gobject-2.0") is not None

ALL_FIXTURES = [
    "sample.pdf",
    *(["sample.docx"] if _HAS_WEASYPRINT_DEPS else []),
    "stress.pdf",
    "running_header.pdf",
    "merged_cells.pdf",
    "with_image.pdf",
    "rotated_page.pdf",
]


@pytest.fixture(scope="module")
def converted():
    """Converts every fixture once; every check below reads from this
    shared result instead of re-converting, so the benchmark stays fast."""
    return {name: convert_document(str(FIXTURES / name)) for name in ALL_FIXTURES}


def _heading_levels(markdown: str) -> list[int]:
    return [len(m.group(1)) for m in re.finditer(r"^(#+)\s", markdown, re.MULTILINE)]


def _table_blocks(markdown: str) -> list[list[str]]:
    """Groups consecutive `|`-prefixed lines into separate table blocks."""
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in markdown.splitlines():
        if line.strip().startswith("|"):
            current.append(line)
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return blocks


def _is_separator_row(line: str) -> bool:
    return bool(re.fullmatch(r"\|[\s:|-]+\|", line.strip()))


class TestHeadingHierarchy:
    """See CONTRACT.md: "Heading hierarchy"."""

    def test_no_level_skips_greater_than_one(self, converted):
        for name, result in converted.items():
            deepest_so_far = 0
            for level in _heading_levels(result.markdown):
                assert level <= deepest_so_far + 1, (
                    f"{name}: heading jumps to H{level} from deepest-seen H{deepest_so_far}"
                )
                deepest_so_far = max(deepest_so_far, level)

    def test_no_orphaned_empty_headings(self, converted):
        for name, result in converted.items():
            assert not re.search(r"^#+\s*$", result.markdown, re.MULTILINE), (
                f"{name}: orphaned empty heading"
            )

    def test_no_immediate_duplicate_headings(self, converted):
        for name, result in converted.items():
            heading_lines = re.findall(r"^(#+\s+.+)$", result.markdown, re.MULTILINE)
            for a, b in zip(heading_lines, heading_lines[1:], strict=False):
                assert a != b, f"{name}: immediately duplicated heading {a!r}"


class TestTableStructure:
    """See CONTRACT.md: "Table structure"."""

    def test_consistent_column_count_per_table(self, converted):
        for name, result in converted.items():
            for block in _table_blocks(result.markdown):
                header_cols = block[0].count("|")
                for row in block:
                    assert row.count("|") == header_cols, (
                        f"{name}: table row {row!r} has {row.count('|')} pipes, "
                        f"header has {header_cols}"
                    )

    def test_no_stray_separator_row_rendered_as_data(self, converted):
        for name, result in converted.items():
            for block in _table_blocks(result.markdown):
                # At most one separator row (the header's), and it must be
                # the second line of the block if present at all.
                separator_positions = [i for i, row in enumerate(block) if _is_separator_row(row)]
                assert separator_positions in ([], [1]), (
                    f"{name}: unexpected separator row(s) at {separator_positions} in table {block!r}"
                )


class TestImageReferences:
    """See CONTRACT.md: "Image references"."""

    def test_no_malformed_empty_image_syntax(self, converted):
        for name, result in converted.items():
            assert "![]()" not in result.markdown, f"{name}: malformed empty image reference"


class TestProvenance:
    """See CONTRACT.md: "Provenance"."""

    def test_every_conversion_reports_full_provenance(self, converted):
        expected_keys = {
            "docmd_version",
            "backend",
            "backend_version",
            "ocr_used",
            "conversion_duration_ms",
        }
        for name, result in converted.items():
            missing = expected_keys - result.provenance.keys()
            assert not missing, f"{name}: provenance missing {missing}"


class TestPageRotation:
    """See CONTRACT.md: "Page rotation: not a gap"."""

    def test_rotated_page_text_present_and_upright(self, converted):
        result = converted["rotated_page.pdf"]
        assert "first page, and it is not rotated" in result.markdown
        assert "its /Rotate flag is set to ninety" in result.markdown
