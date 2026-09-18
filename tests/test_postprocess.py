from docmd.postprocess.heading_normalize import normalize_headings
from docmd.postprocess.image_handling import apply_image_handling
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
    lines = [l for l in out.splitlines() if l.strip()]
    assert lines == [
        "| Attention(Q, K, V) = softmax(...)V | (1) |",
        "| --- | --- |",
    ]
