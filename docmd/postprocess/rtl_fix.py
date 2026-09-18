"""Fixes reversed citation-style brackets that appear in right-to-left (RTL)
script documents.

Found via a real Arabic Wikipedia article: LTR punctuation (square brackets
wrapping a citation number, sometimes itself a Markdown link to a footnote)
embedded in RTL text comes out of extraction in reversed order - `][1](url)[`
instead of `[1](url)`. This is a Unicode bidirectional-text extraction
artifact, not something docmd invented a name for; the underlying PDF text
stream doesn't preserve enough information to run a full, correct
bidirectional-algorithm pass after the fact.

Only the square-bracket case is fixed here. The same reversal affects
parentheses in RTL text (e.g. `)6,000 km2(` instead of `(6,000 km2)`), but a
`)...( -> (...)` swap is far riskier: legitimate prose regularly places two
independent parentheticals back to back - "word (first) and (second)" - which
a naive reversal-swap would corrupt. Square brackets don't have that
ambiguity in Markdown: a correctly-ordered link or reference always starts
with `[`, never `]`, so a `]...[` span can only be this artifact, not
legitimate content. Left undocumented as fixed for parentheses - see
CONTRACT.md.
"""

from __future__ import annotations

import re

# Matches a reversed span: `]`, then either one-or-more complete Markdown
# links back to back (no bracket characters inside each link's own label or
# URL) or a bare short number (a citation marker with no hyperlink), then
# `[`. This shape cannot occur in correctly-ordered Markdown - a real link
# or reference always opens with `[` - so every match here is the
# bidirectional-extraction artifact, never legitimate content.
_REVERSED_CITATION_RE = re.compile(
    r"\]((?:\[[^\[\]]*\]\([^()]*\))+|\d{1,3})\["
)


def fix_rtl_brackets(markdown: str) -> str:
    """Swaps reversed `]...[ ` citation spans back to the correct `[...]`
    order. A no-op on documents that never produce this shape (i.e.
    everything without RTL-embedded LTR punctuation)."""
    return _REVERSED_CITATION_RE.sub(lambda m: "[" + m.group(1) + "]", markdown)
