"""Unit tests for docmd/heading_numbering.py - the shared section-number
logic behind both the Markdown heading pass and RAG chunk breadcrumbs."""

from __future__ import annotations

import pytest

from docmd.heading_numbering import NumberingLevels, numbering_depth


@pytest.mark.parametrize(
    ("text", "depth"),
    [
        ("5.4. Error Handling", 2),
        ("5.4.1. Connection Error Handling", 3),
        ("3.2 Attention", 2),
        ("3 Model Architecture", 1),
        ("5. Streams and Multiplexing", 1),
        ("2024 Outlook", None),  # 4 digits: a year, not a section number
        ("Introduction", None),
        ("Abstract", None),
        ("CHAPTER IV", None),
        ('<span id="p-1"></span>**[5.4. Error Handling](#p-1)**', 2),  # Marker's wrapping
    ],
)
def test_numbering_depth(text, depth):
    assert numbering_depth(text) == depth


def test_first_top_level_heading_takes_the_callers_hint():
    levels = NumberingLevels()
    assert levels.resolve("1 Introduction", hint=2) == 2


def test_later_headings_at_the_same_depth_reuse_the_learned_level():
    """Found on a real arXiv paper: "1 Introduction" got level 2 but
    "6 Results" got level 1 from Marker - same kind of heading, different
    level. The first one seen fixes the level for the rest."""
    levels = NumberingLevels()
    levels.resolve("1 Introduction", hint=2)
    assert levels.resolve("6 Results", hint=1) == 2


def test_dotted_child_goes_one_level_below_its_bare_number_parent():
    levels = NumberingLevels()
    levels.resolve("3 Model Architecture", hint=2)
    assert levels.resolve("3.1 Encoder", hint=2) == 3
    assert levels.resolve("3.2.1 Scaled Dot-Product", hint=2) == 4


def test_without_a_known_parent_a_dotted_heading_falls_back_to_its_depth():
    levels = NumberingLevels()
    assert levels.resolve("5.3. Prioritization", hint=9) == 2


def test_unnumbered_heading_resolves_to_none():
    assert NumberingLevels().resolve("Abstract", hint=1) is None
