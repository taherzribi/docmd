"""Table cleanup: fixes the two most common ways Marker's tables come out
mangled for complex layouts:

  1. Ragged / malformed structure - a missing or malformed separator row,
     or data rows with more or fewer cells than the header.
  2. A single logical table split into two because it spans a page break -
     Marker (reasonably) treats each page independently, so a table that
     continues onto the next page comes out as two separate tables, each
     with its own repeated header row.

Operates on already-rendered Markdown text rather than Marker's internal
block tree, so it works standalone on any Markdown, not just docmd's own
output - and keeps this module decoupled from Marker's internals.
"""

from __future__ import annotations

import re

_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_SEP_CELL_RE = re.compile(r"^:?-+:?$")
_PAGE_SEPARATOR = "-" * 48


def _is_row(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and "|" in stripped


def _split_cells(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _is_separator_row(line: str) -> bool:
    cells = _split_cells(line)
    return bool(cells) and all(_SEP_CELL_RE.match(c) for c in cells)


def _render_row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _normalize_block(header: list[str], data_rows: list[list[str]]) -> list[str]:
    """Pad/truncate every row to the header's column count and re-render
    with a clean separator row."""
    col_count = len(header)
    out = [_render_row(header), _render_row(["---"] * col_count)]
    for row in data_rows:
        if len(row) < col_count:
            row = row + [""] * (col_count - len(row))
        elif len(row) > col_count:
            row = row[:col_count]
        out.append(_render_row(row))
    return out


def _headers_match(a: list[str], b: list[str]) -> bool:
    norm = lambda cells: [c.strip().lower() for c in cells]
    return norm(a) == norm(b)


def clean_tables(markdown: str) -> str:
    """Return `markdown` with pipe-table structure fixed up, including
    re-joining tables that were split across a page break."""
    lines = markdown.splitlines()
    out: list[str] = []
    i = 0
    in_fence = False

    while i < len(lines):
        line = lines[i]

        if _FENCE_RE.match(line):
            in_fence = not in_fence
            out.append(line)
            i += 1
            continue
        if in_fence:
            out.append(line)
            i += 1
            continue

        if not (_is_row(line) and i + 1 < len(lines) and _is_row(lines[i + 1])):
            out.append(line)
            i += 1
            continue

        # Found the start of a table block: header + at least one more row.
        header = _split_cells(line)
        j = i + 1
        if _is_separator_row(lines[j]):
            j += 1
        block_end = j
        while block_end < len(lines) and _is_row(lines[block_end]):
            block_end += 1
        # A stray extra separator row (found via a real two-column paper: a
        # single-row "table" - actually a numbered equation - with two
        # separator rows back to back and no real data) would otherwise get
        # treated as a literal data row of dashes. Drop any row that's
        # itself separator-shaped rather than rendering it as content.
        data_rows = [
            _split_cells(l) for l in lines[j:block_end] if not _is_separator_row(l)
        ]

        # Look ahead past blank lines / Marker's page separator for a
        # continuation: another table block whose header repeats this one.
        k = block_end
        while True:
            probe = k
            while probe < len(lines) and (
                not lines[probe].strip() or lines[probe].strip() == _PAGE_SEPARATOR
            ):
                probe += 1
            if not (probe < len(lines) and _is_row(lines[probe]) and probe + 1 < len(lines) and _is_row(lines[probe + 1])):
                break
            next_header = _split_cells(lines[probe])
            if not _headers_match(header, next_header):
                break
            p = probe + 1
            if _is_separator_row(lines[p]):
                p += 1
            next_block_end = p
            while next_block_end < len(lines) and _is_row(lines[next_block_end]):
                next_block_end += 1
            data_rows.extend(
                _split_cells(l)
                for l in lines[p:next_block_end]
                if not _is_separator_row(l)
            )
            k = next_block_end

        out.extend(_normalize_block(header, data_rows))
        i = k

    return "\n".join(out) + ("\n" if markdown.endswith("\n") else "")
