"""Heading normalization: docmd's fix for Marker's most common structural
quirks in raw output - headings that skip levels (H1 -> H3), the same
section header repeated verbatim right after itself (Marker sometimes turns
a running page header into a heading on every page), and stray '#' markers
with no text. None of this is Marker's fault exactly - it's an artifact of
reconstructing structure from visual layout - but it's exactly the kind of
thing that makes raw conversion output bad for RAG chunking, where heading
level is often used to decide chunk boundaries.
"""

from __future__ import annotations

import re

from docmd.heading_numbering import NumberingLevels

_ATX_RE = re.compile(r"^(#{1,6})\s*(.*?)\s*$")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")


def normalize_headings(markdown: str) -> str:
    """Return `markdown` with heading levels and duplicates cleaned up.

    Rules applied, line by line (skipping the contents of fenced code blocks,
    since a '#' there is a comment/directive, not a heading):
      1. A heading with no text after the '#'s is dropped.
      2. A heading level may increase by at most 1 relative to the deepest
         heading seen so far (H1 -> H3 becomes H1 -> H2), preventing
         orphaned levels. Decreasing back to any shallower level is always
         allowed.
      3. A heading whose text exactly repeats the immediately preceding
         heading's text (ignoring blank lines between them) is dropped,
         regardless of level - this is Marker turning a repeated running
         page header into a heading on every page.
      4. Spacing after '#' is normalized to exactly one space.
    """
    lines = markdown.splitlines()
    out: list[str] = []
    last_level = 0
    numbering = NumberingLevels()
    last_heading_text: str | None = None
    in_fence = False

    for line in lines:
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence:
            out.append(line)
            continue

        match = _ATX_RE.match(line)
        if not match:
            out.append(line)
            if line.strip():
                # Any real content resets "last heading" adjacency, so a
                # heading appearing after body text is never treated as a
                # duplicate of one seen much earlier.
                last_heading_text = None
            continue

        level = len(match.group(1))
        text = match.group(2).strip(" \t#")

        if not text:
            continue  # drop orphaned '#' with no content

        if text == last_heading_text:
            continue  # drop immediate duplicate heading

        clamped = min(level, last_level + 1)
        resolved = numbering.resolve(text, clamped)
        level = min(resolved, 6) if resolved is not None else clamped  # ATX caps at 6 '#'

        last_level = level
        last_heading_text = text
        out.append("#" * level + " " + text)

    return "\n".join(out) + ("\n" if markdown.endswith("\n") else "")
