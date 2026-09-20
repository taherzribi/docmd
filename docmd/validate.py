"""`docmd validate file.pdf` - runs the same structural checks that guard
docmd's own contract (see CONTRACT.md, tests/test_benchmark.py) against a
document a user actually converted, reporting concrete findings rather than
an invented quality percentage.

Deliberately not a numeric score: docmd has no ground truth for "is this
text correct," so anything framed as a confidence percentage would be
fabricated. Every finding here is a specific, verifiable structural fact
about the Markdown - the same kind of fact CONTRACT.md's guarantees are
built from.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_HEADING_RE = re.compile(r"^(#+)\s", re.MULTILINE)
_EMPTY_HEADING_RE = re.compile(r"^#+\s*$", re.MULTILINE)
_HEADING_LINE_RE = re.compile(r"^(#+\s+.+)$", re.MULTILINE)
_SEPARATOR_ROW_RE = re.compile(r"^\|[\s:|-]+\|$")


@dataclass
class Finding:
    ok: bool
    message: str


@dataclass
class ValidationReport:
    findings: list[Finding]

    @property
    def has_warnings(self) -> bool:
        return any(not f.ok for f in self.findings)


def _heading_levels(markdown: str) -> list[int]:
    return [len(m.group(1)) for m in _HEADING_RE.finditer(markdown)]


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
    return bool(_SEPARATOR_ROW_RE.fullmatch(line.strip()))


def validate_markdown(markdown: str) -> ValidationReport:
    findings: list[Finding] = []

    levels = _heading_levels(markdown)
    skips = 0
    deepest_so_far = 0
    for level in levels:
        if level > deepest_so_far + 1:
            skips += 1
        deepest_so_far = max(deepest_so_far, level)
    if skips:
        findings.append(Finding(False, f"{skips} heading level skip(s) greater than one"))
    else:
        findings.append(Finding(True, f"{len(levels)} heading(s) detected, no level skips"))

    if _EMPTY_HEADING_RE.search(markdown):
        findings.append(Finding(False, "orphaned empty heading(s) found"))

    heading_lines = _HEADING_LINE_RE.findall(markdown)
    duplicates = sum(1 for a, b in zip(heading_lines, heading_lines[1:], strict=False) if a == b)
    if duplicates:
        findings.append(Finding(False, f"{duplicates} immediately duplicated heading(s)"))

    blocks = _table_blocks(markdown)
    inconsistent = 0
    stray_separators = 0
    for block in blocks:
        header_cols = block[0].count("|")
        if any(row.count("|") != header_cols for row in block):
            inconsistent += 1
        separator_positions = [i for i, row in enumerate(block) if _is_separator_row(row)]
        if separator_positions not in ([], [1]):
            stray_separators += 1
    if inconsistent:
        findings.append(Finding(False, f"{inconsistent} table(s) have inconsistent column counts"))
    elif blocks:
        findings.append(Finding(True, f"{len(blocks)} table(s), all consistent column counts"))
    if stray_separators:
        findings.append(Finding(False, f"{stray_separators} table(s) have a stray separator row"))

    if "![]()" in markdown:
        findings.append(Finding(False, "malformed empty image reference(s) found"))

    return ValidationReport(findings=findings)
