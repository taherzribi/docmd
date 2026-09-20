"""A heading's own visible section number as a structural signal, shared by
the Markdown heading pass (`postprocess/heading_normalize.py`) and RAG chunk
section breadcrumbs (`converters/chunk_extraction.py`).

Marker infers heading depth from visual layout, which is noisy: found via a
real RFC and a real arXiv paper, it gave "5.4 Error Handling" the same level
as the deeper "5.3.1"/"5.3.2" before it, and gave "1 Introduction" and
"6 Results" different levels despite being the same kind of heading. A
section number is unambiguous where the visual guess isn't - but only its
*relative* structure is trustworthy ("5.4" sits one level under "5"), not
any absolute level, since a document title or abstract may occupy the levels
above it.

So levels are learned per numbering depth rather than computed from the
number: the first heading seen at a depth fixes that depth's level (a
top-level "1 Introduction" takes the caller's best guess; "3.1" takes its
parent's level plus one), and every later heading at the same depth reuses it.
That keeps a bare-number parent ("3 Model Architecture") in the breadcrumb
above its dotted children instead of being evicted by them.
"""

from __future__ import annotations

import re

_DOTTED_RE = re.compile(r"^(\d+(?:\.\d+)+)\.?\s")
# 1-2 digits then a letter: "3 Model Architecture", "5. Streams". Deliberately
# not 3+ digits ("2024 Outlook") or a digit run into another digit - too
# ambiguous a signal to treat as a section number.
_BARE_RE = re.compile(r"^(\d{1,2})\.?\s+[^\W\d_]")
# Marker wraps a heading's visible text in an HTML anchor span and/or
# Markdown bold/link syntax (`<span id="p-1"></span>**[5.4. Error
# Handling](#p-1)**`); stripped only to find the number, not to change what
# gets rendered.
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_LEADING_DECORATION_RE = re.compile(r"^[\s*_\[\]]+")


def numbering_depth(text: str) -> int | None:
    """Depth implied by a leading section number: "5" -> 1, "5.4" -> 2,
    "5.4.1" -> 3. None when the heading has no recognizable number."""
    cleaned = _LEADING_DECORATION_RE.sub("", _HTML_TAG_RE.sub("", text))
    dotted = _DOTTED_RE.match(cleaned)
    if dotted:
        return dotted.group(1).count(".") + 1
    if _BARE_RE.match(cleaned):
        return 1
    return None


class NumberingLevels:
    """One instance per document. Learns which level each numbering depth
    lives at, from the first heading seen at that depth."""

    def __init__(self) -> None:
        self._level_by_depth: dict[int, int] = {}

    def resolve(self, text: str, hint: int) -> int | None:
        """The level `text` should have, or None if it isn't numbered.
        `hint` is the caller's best guess for a top-level (depth 1) heading
        that has nothing to be relative to yet."""
        depth = numbering_depth(text)
        if depth is None:
            return None
        level = self._level_by_depth.get(depth)
        if level is None:
            parent = self._level_by_depth.get(depth - 1)
            if parent is not None:
                level = parent + 1
            elif depth == 1:
                level = hint
            else:
                level = depth
            self._level_by_depth[depth] = level
        return level
