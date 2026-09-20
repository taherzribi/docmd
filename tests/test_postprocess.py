from docmd.postprocess.heading_normalize import normalize_headings
from docmd.postprocess.image_handling import apply_image_handling
from docmd.postprocess.rtl_fix import fix_rtl_brackets
from docmd.postprocess.table_cleanup import clean_tables


def test_heading_normalize_fixes_level_skip():
    md = "# Title\n### Subsection\n"
    out = normalize_headings(md)
    assert out == "# Title\n## Subsection\n"


def test_heading_normalize_fixes_level_skip_then_leaves_recovered_depth_alone():
    """The exact pattern found in a real 27-page IMF report while stress-
    testing against downloaded (not synthetic) documents: an H1 jumps
    straight to H4 (skipping H2/H3), gets clamped to H2 - but a *later*
    heading that's also originally H4 is left alone, because an H3 heading
    in between legitimately re-establishes the depth. Never reproduced
    synthetically (see skip_headings.pdf in git history, removed after
    Marker's own layout model wouldn't cooperate) - this encodes the real
    structure without redistributing the copyrighted source PDF."""
    md = (
        "# Summary of the Economy Classification\n"
        "#### General Features and Composition of Groups\n"
        "### Advanced Economies\n"
        "#### Emerging Market and Developing Economies\n"
    )
    out = normalize_headings(md)
    assert out == (
        "# Summary of the Economy Classification\n"
        "## General Features and Composition of Groups\n"
        "### Advanced Economies\n"
        "#### Emerging Market and Developing Economies\n"
    )


def test_heading_normalize_trusts_visible_numbering_over_wrong_backend_level():
    """The exact pattern found in a real RFC (RFC 9113) and confirmed again
    in a real arXiv paper ("Attention Is All You Need"): Marker assigned
    "5.4 Error Handling" the *same* level as the deeper "5.3.1"/"5.3.2"
    right before it - not a level *skip* (the clamp above doesn't catch
    it), just a wrong absolute level, rendering "5.4" one level too deep
    instead of alongside its true sibling "5.3". A heading's own visible
    dotted-decimal numbering is unambiguous ground truth for its depth,
    unlike Marker's visually-inferred level - trusted here instead."""
    md = (
        "## 5.3. Prioritization\n"
        "### 5.3.1. Background\n"
        "### 5.3.2. Priority Signaling\n"
        "### 5.4. Error Handling\n"  # wrong: Marker gave this H3, same as 5.3.x
        "#### 5.4.1. Connection Error Handling\n"
    )
    out = normalize_headings(md)
    assert out == (
        "## 5.3. Prioritization\n"
        "### 5.3.1. Background\n"
        "### 5.3.2. Priority Signaling\n"
        "## 5.4. Error Handling\n"
        "### 5.4.1. Connection Error Handling\n"
    )


def test_heading_normalize_numbering_override_sees_past_html_and_markdown_wrapping():
    """Marker wraps real heading text in an HTML anchor span and Markdown
    bold/link syntax - the numbering-depth override has to look past that
    decoration to find the leading number, not just fail silently."""
    md = (
        '## <span id="a"></span>**[5.3. Prioritization](#a)**\n'
        '### <span id="b"></span>**[5.4. Error Handling](#b)**\n'
    )
    out = normalize_headings(md)
    assert '## <span id="b"></span>**[5.4. Error Handling](#b)**' in out


def test_heading_normalize_ignores_bare_numbers_with_no_embedded_dot():
    """A heading that merely starts with a bare number ("2024 Outlook") is
    too ambiguous a signal for nesting depth - the override requires at
    least one embedded dot (a real multi-segment section number) before it
    touches the level Marker assigned."""
    md = "# Report\n### 2024 Outlook\n"
    out = normalize_headings(md)
    # Falls back to the ordinary skip-clamp, not the numbering override.
    assert out == "# Report\n## 2024 Outlook\n"


def test_heading_normalize_drops_empty_heading():
    md = "# Title\n##\nBody text.\n"
    out = normalize_headings(md)
    assert "##\n" not in out
    assert "Body text." in out


def test_heading_normalize_drops_immediate_duplicate():
    md = "# Report\n\n# Report\n\nBody.\n"
    out = normalize_headings(md)
    assert out.count("# Report") == 1


def test_heading_normalize_keeps_non_adjacent_repeats():
    md = "# Intro\n\nBody.\n\n# Intro\n"
    out = normalize_headings(md)
    # Same text, but real content came between - not a duplicate.
    assert out.count("# Intro") == 2


def test_heading_normalize_ignores_hash_inside_code_fence():
    md = "# Title\n```\n# not a heading\n```\n"
    out = normalize_headings(md)
    assert "# not a heading" in out


def test_clean_tables_synthesizes_missing_separator():
    md = "| A | B |\n| 1 | 2 |\n"
    out = clean_tables(md)
    lines = out.strip().splitlines()
    assert lines[0] == "| A | B |"
    assert lines[1] == "| --- | --- |"
    assert lines[2] == "| 1 | 2 |"


def test_clean_tables_pads_ragged_rows():
    md = "| A | B | C |\n| --- | --- | --- |\n| 1 | 2 |\n| x | y | z |\n"
    out = clean_tables(md)
    lines = out.strip().splitlines()
    assert lines[2] == "| 1 | 2 |  |"


def test_clean_tables_merges_tables_split_by_page_break():
    md = (
        "| A | B |\n"
        "| --- | --- |\n"
        "| 1 | 2 |\n"
        "\n"
        + "-" * 48
        + "\n\n"
        "| A | B |\n"
        "| --- | --- |\n"
        "| 3 | 4 |\n"
    )
    out = clean_tables(md)
    lines = out.strip().splitlines()
    assert lines == [
        "| A | B |",
        "| --- | --- |",
        "| 1 | 2 |",
        "| 3 | 4 |",
    ]


def test_clean_tables_does_not_merge_distinct_tables():
    md = "| A | B |\n| --- | --- |\n| 1 | 2 |\n\n| X | Y |\n| --- | --- |\n| 9 | 8 |\n"
    out = clean_tables(md)
    assert out.count("| A | B |") == 1
    assert out.count("| X | Y |") == 1


def test_image_handling_placeholder_mode():
    md = "See figure: ![a chart](_page_0_Figure_1.jpeg)"
    out = apply_image_handling(md, images={}, mode="placeholder")
    assert "![" not in out
    assert "a chart omitted" in out


def test_image_handling_skip_mode_removes_reference():
    md = "Before ![](img.png) after."
    out = apply_image_handling(md, images={}, mode="skip")
    assert "img.png" not in out
    assert "Before" in out and "after." in out


def test_image_handling_alt_text_mode_fills_empty_alt():
    md = "![](img.png)"
    out = apply_image_handling(md, images={}, mode="alt-text")
    assert out == "![Image 1](img.png)"


def test_image_handling_drops_fully_empty_image_reference():
    """Real Marker output on a scanned page: `![]()` with no href at all,
    directly adjacent to a real image reference with no separator between
    them - found while OCR-testing a genuinely scanned PDF. The old regex
    required at least one character inside the parens, so `![]()` never
    matched and leaked through every mode unprocessed."""
    md = "![]()![](real.jpeg)"

    assert apply_image_handling(md, images={}, mode="placeholder") == "*[image omitted]*"
    assert apply_image_handling(md, images={}, mode="skip") == ""
    assert apply_image_handling(md, images={}, mode="alt-text") == "![Image 1](real.jpeg)"


def test_clean_tables_drops_stray_duplicate_separator_row():
    """Real Marker output found stress-testing a real two-column paper
    ("Attention Is All You Need"): a single-row "table" - actually a
    numbered equation rendered as a 1-cell table - came out with two
    separator rows back to back and no real data row. The old code treated
    the second separator as a literal data row and printed a row of dashes
    into the output."""
    md = (
        "| Attention(Q, K, V) = softmax(...)V | (1) |\n"
        "|----------------------------------------|-----|\n"
        "|----------------------------------------|-----|\n"
    )
    out = clean_tables(md)
    lines = [line for line in out.splitlines() if line.strip()]
    assert lines == [
        "| Attention(Q, K, V) = softmax(...)V | (1) |",
        "| --- | --- |",
    ]


def test_fix_rtl_brackets_swaps_reversed_citation_link():
    """Real Marker output found converting a real Arabic Wikipedia article:
    a citation number linked to a footnote came out with its wrapping
    brackets reversed - `][1](#page-21-0)[` instead of `[1](#page-21-0)` - a
    bidirectional-text extraction artifact from LTR punctuation embedded in
    RTL script. The fixed form wraps the link in a literal `[...]` pair,
    which renders as the clickable "[1]" Wikipedia's own citation style
    shows - not a bare unwrapped link."""
    md = "جبل كاترين ][1](#page-21-0)[ متر"
    assert fix_rtl_brackets(md) == "جبل كاترين [[1](#page-21-0)] متر"


def test_fix_rtl_brackets_swaps_bare_number_citation():
    """Same bug, but for a citation marker with no hyperlink at all - a bare
    number, still reversed the same way."""
    md = "النيل وأرض النيل ]36[ حرفي"
    assert fix_rtl_brackets(md) == "النيل وأرض النيل [36] حرفي"


def test_fix_rtl_brackets_handles_adjacent_reversed_citations():
    """Real Marker output: three citation markers chained together, only
    the last two of which happened to be reversed - each one is fixed
    independently without the fix bleeding across the boundary."""
    md = "[24](#page-22-11)][23](#page-22-10)[][22](#page-22-9)["
    assert fix_rtl_brackets(md) == "[24](#page-22-11)[[23](#page-22-10)][[22](#page-22-9)]"


def test_fix_rtl_brackets_leaves_normal_markdown_links_alone():
    """The pattern this targets (`]...[`) can only occur from the reversal
    artifact - a correctly-ordered link always starts with `[`, never `]` -
    so ordinary prose and links must pass through completely unchanged."""
    md = "See [the docs](https://example.com/docs) for more, and [1](#fn1)[2](#fn2) too."
    assert fix_rtl_brackets(md) == md


def test_clean_tables_strips_dot_leader_filler_from_cells():
    """Real Marker output found converting a real Berkshire Hathaway
    shareholder letter: a dot-leader-style table (a year label, then a long
    run of dots for visual alignment, then the value - no gridlines in the
    source PDF) came out with the literal dot-leader characters inside the
    cell's text, e.g. '1965 ........................'."""
    md = (
        "| Year | Change |\n"
        "| --- | --- |\n"
        "| 1965 ........................................................ | 49.5 |\n"
    )
    out = clean_tables(md)
    assert "1965 ...." not in out
    assert "| 1965 | 49.5 |" in out


def test_clean_tables_does_not_strip_a_normal_ellipsis():
    """Only 4+ consecutive dot-leaders are stripped - a standard 3-dot
    prose ellipsis is real content, not visual filler."""
    md = "| Note | Detail |\n| --- | --- |\n| See more... | ok |\n"
    out = clean_tables(md)
    assert "See more..." in out

