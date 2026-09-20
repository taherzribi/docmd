"""Extracts Markdown pipe-tables as CSV - `docmd extract file.pdf --tables csv`.

Operates on already-postprocessed Markdown (after `clean_tables` has run),
so every table it sees here is already normalized: consistent column
count, a single separator row, no page-split duplicates left to merge.
Deliberately doesn't share code with `postprocess/table_cleanup.py` (whose
job is fixing *messy* raw tables) beyond the same handful of tiny line-level
helpers - keeps this module simple, since by this point there's nothing
messy left to handle.
"""

from __future__ import annotations

import csv
import io
import re

_SEP_CELL_RE = re.compile(r"^:?-+:?$")
# CommonMark backslash-escapes punctuation that would otherwise be
# significant Markdown syntax - e.g. a dollar figure renders as `\$ 5,428`
# so a Markdown/KaTeX renderer doesn't treat `$` as a math delimiter. Correct
# in Markdown; meaningless (and wrong) once re-purposed as CSV, which has no
# such escaping convention, so it's undone for this output only.
_MARKDOWN_ESCAPE_RE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!$])")


def _is_row(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and "|" in stripped


def _split_cells(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [_MARKDOWN_ESCAPE_RE.sub(r"\1", cell.strip()) for cell in stripped.split("|")]


def _is_separator_row(line: str) -> bool:
    cells = _split_cells(line)
    return bool(cells) and all(_SEP_CELL_RE.match(c) for c in cells)


def extract_tables_as_csv(markdown: str) -> list[str]:
    """Returns one CSV-formatted string per table found in `markdown`, in
    document order."""
    lines = markdown.splitlines()
    tables: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        if not (_is_row(line) and i + 1 < len(lines) and _is_separator_row(lines[i + 1])):
            i += 1
            continue

        rows = [_split_cells(line)]
        j = i + 2
        while j < len(lines) and _is_row(lines[j]):
            rows.append(_split_cells(lines[j]))
            j += 1

        buffer = io.StringIO()
        csv.writer(buffer).writerows(rows)
        tables.append(buffer.getvalue())
        i = j

    return tables
