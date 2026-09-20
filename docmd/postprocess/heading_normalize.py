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

_ATX_RE = re.compile(r"^(#{1,6})\s*(.*?)\s*$")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")
# A heading's own visible numbering ("5.4", "5.4.1") is unambiguous ground
# truth for its nesting depth - unlike Marker's visually-inferred heading
# level, which can assign a *reachable* but wrong absolute level (found via
# a real RFC: "5.4 Error Handling" got the same level as "5.3.1"/"5.3.2"
# right before it, rendering one level too deep instead of alongside "5.3" -
# a defect the skip-clamp below doesn't catch, since 5.4's level wasn't a
# *skip* from the previous heading, just wrong). Requires at least one
# embedded dot (two-plus segments) so a heading merely starting with a bare
# number ("2024 Outlook") - too ambiguous a signal for nesting depth - never
# triggers this override. See docmd/converters/chunk_extraction.py, which
# applies the identical rule to RAG chunk section breadcrumbs.
_NUMBERING_RE = re.compile(r"^(\d+(?:\.\d+)+)\.?\s")
# Marker wraps a heading's visible text in an HTML anchor span and/or
# Markdown bold/link syntax (e.g. `<span id="page-22-0"></span>**[5.4. Error
# Handling](#page-22-0)**`) - stripped here only to detect the numbering
# pattern, not to change what actually gets rendered.
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_LEADING_MARKDOWN_DECORATION_RE = re.compile(r"^[\s*_\[\]]+")


def _numbering_depth(text: str) -> int | None:
    cleaned = _HTML_TAG_RE.sub("", text)
    cleaned = _LEADING_MARKDOWN_DECORATION_RE.sub("", cleaned)
    match = _NUMBERING_RE.match(cleaned)
    return match.group(1).count(".") + 1 if match else None


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

        numbering_depth = _numbering_depth(text)
        if numbering_depth is not None:
            level = min(numbering_depth, 6)  # ATX headings cap at 6 '#'
        elif level > last_level + 1:
            level = last_level + 1

        last_level = level
        last_heading_text = text
        out.append("#" * level + " " + text)

    return "\n".join(out) + ("\n" if markdown.endswith("\n") else "")
