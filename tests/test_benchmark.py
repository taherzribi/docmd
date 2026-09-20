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
from docmd.config import ConvertConfig
from docmd.converters.base import CONTENT_TYPES
from docmd.validate import _heading_levels, _is_separator_row, _table_blocks

FIXTURES = Path(__file__).parent / "fixtures"

# sample.docx goes through weasyprint, which needs native Pango/GObject/Cairo
# libraries pip can't install - see tests/test_converters.py for the same
# check. Excluded from the corpus rather than failing on an environment gap
# that isn't a docmd bug; CI has these libraries installed.
_HAS_WEASYPRINT_DEPS = ctypes.util.find_library("gobject-2.0") is not None

ALL_FIXTURES = [
    "sample.pdf",
    *(["sample.docx", "sample.pptx"] if _HAS_WEASYPRINT_DEPS else []),
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


@pytest.fixture(scope="module")
def converted_with_chunks():
    config = ConvertConfig(include_chunks=True)
    return {name: convert_document(str(FIXTURES / name), config=config) for name in ALL_FIXTURES}


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


class TestRAGChunks:
    """See CONTRACT.md: "RAG chunks"."""

    def test_content_type_always_in_stable_vocabulary(self, converted_with_chunks):
        for name, result in converted_with_chunks.items():
            for chunk in result.chunks:
                assert chunk.content_type in CONTENT_TYPES, (
                    f"{name}: {chunk.content_type!r} not in the stable vocabulary"
                )

    def test_repeated_page_header_never_becomes_its_own_chunk(self, converted_with_chunks):
        result = converted_with_chunks["running_header.pdf"]
        assert all("CONFIDENTIAL" not in chunk.text for chunk in result.chunks)

    def test_chunks_none_without_include_chunks(self, converted):
        for name, result in converted.items():
            assert result.chunks is None, f"{name}: chunks populated without include_chunks=True"


class TestChunkMerging:
    """See CONTRACT.md: "Chunk merging"."""

    def test_tables_and_images_survive_a_huge_token_budget_unchanged(self):
        """A merge pass generous enough to absorb the entire rest of the
        document (100k tokens) still must not touch table/image chunks -
        proves the exclusion isn't just "rarely triggered by a normal
        budget", by removing the budget as a variable entirely."""
        unmerged_config = ConvertConfig(include_chunks=True)
        merged_config = ConvertConfig(include_chunks=True, chunk_max_tokens=100_000)
        for name in ["stress.pdf", "with_image.pdf", "merged_cells.pdf"]:
            unmerged = convert_document(str(FIXTURES / name), config=unmerged_config)
            merged = convert_document(str(FIXTURES / name), config=merged_config)
            unmerged_non_text = [c for c in unmerged.chunks if c.content_type in {"table", "image", "list"}]
            merged_non_text = [c for c in merged.chunks if c.content_type in {"table", "image", "list"}]
            assert [c.text for c in unmerged_non_text] == [c.text for c in merged_non_text], (
                f"{name}: table/image/list chunk text changed after merging"
            )


class TestValidate:
    """docmd validate reuses these exact checks - see docmd/validate.py.
    Nothing in the fixture corpus should ever raise a warning; if it does,
    either a real regression was introduced, or the fixture legitimately
    needs updating (and this test's expectation with it)."""

    def test_no_fixture_produces_a_validation_warning(self, converted):
        from docmd.validate import validate_markdown

        for name, result in converted.items():
            report = validate_markdown(result.markdown)
            warnings = [f.message for f in report.findings if not f.ok]
            assert not warnings, f"{name}: unexpected validation warning(s): {warnings}"
