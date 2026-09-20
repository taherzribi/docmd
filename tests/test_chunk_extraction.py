"""Unit tests for docmd/converters/chunk_extraction.py's section-breadcrumb
logic, using lightweight stubs for Marker's block/document objects instead
of a real PDF conversion - extract_chunks() only touches a handful of
attributes (block_type.name, heading_level, raw_text(), polygon,
ignore_for_output, page_id, page.structure), so a stub covers it exactly.

See tests/test_chunks.py for the real-document integration tests (via
ConvertConfig.include_chunks against actual fixtures).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from docmd.converters.chunk_extraction import extract_chunks


@dataclass
class _BlockType:
    name: str


@dataclass
class _Polygon:
    bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)


@dataclass
class _Span:
    font_size: float
    block_type: _BlockType = field(default_factory=lambda: _BlockType("Span"))


@dataclass
class _Block:
    block_type: _BlockType
    text: str
    page_id: int
    heading_level: int | None = None
    ignore_for_output: bool = False
    polygon: _Polygon = field(default_factory=_Polygon)
    font_size: float | None = None

    def raw_text(self, _document):
        return self.text

    def contained_blocks(self, _document):
        return [_Span(self.font_size)] if self.font_size is not None else []


@dataclass
class _Page:
    page_id: int
    structure: list[str]


class _Document:
    def __init__(self, pages: list[_Page], blocks: dict[str, _Block]):
        self.pages = pages
        self._blocks = blocks

    def get_block(self, block_id):
        return self._blocks[block_id]


def _heading(text, level, size=None):
    return _Block(
        block_type=_BlockType("SectionHeader"), text=text, page_id=0, heading_level=level, font_size=size
    )


def _text(text):
    return _Block(block_type=_BlockType("Text"), text=text, page_id=0)


def _build(blocks: list[_Block]) -> list:
    block_map = {str(i): b for i, b in enumerate(blocks)}
    page = _Page(page_id=0, structure=list(block_map.keys()))
    document = _Document(pages=[page], blocks=block_map)
    return extract_chunks(document)


def test_trusts_visible_numbering_over_wrong_backend_level():
    """The exact real-RFC pattern: Marker assigns "5.4" the same level as
    the deeper "5.3.1"/"5.3.2" right before it. The chunk breadcrumb should
    use 5.4's own numbering, not Marker's wrong level 3."""
    chunks = _build(
        [
            _heading("5.3. Prioritization", level=2),
            _heading("5.3.1. Background", level=4),
            _heading("5.3.2. Priority Signaling", level=3),
            _heading("5.4. Error Handling", level=3),  # wrong: same as 5.3.x
            _text("some body text under 5.4"),
        ]
    )
    body_chunk = next(c for c in chunks if c.content_type == "text")
    assert body_chunk.section == "5.4. Error Handling"


def test_falls_back_to_skip_clamp_when_no_numbering_present():
    chunks = _build(
        [
            _heading("Introduction", level=1),
            _heading("Deeply Nested Title", level=4),
            _text("body text"),
        ]
    )
    body_chunk = next(c for c in chunks if c.content_type == "text")
    assert body_chunk.section == "Introduction > Deeply Nested Title"


def test_ignores_bare_number_with_no_embedded_dot():
    chunks = _build(
        [
            _heading("Report", level=1),
            _heading("2024 Outlook", level=4),
            _text("body text"),
        ]
    )
    body_chunk = next(c for c in chunks if c.content_type == "text")
    # Falls back to the skip-clamp (level 4 -> 2), not the numbering override.
    assert body_chunk.section == "Report > 2024 Outlook"


def test_multiline_heading_is_collapsed_to_one_line_in_the_breadcrumb():
    """Found in a real SCOTUS opinion: a case-caption heading wrapped over
    two lines in the PDF put a raw newline inside every later chunk's
    section string."""
    chunks = _build(
        [
            _heading("GOLDEY, ASSOCIATE WARDEN, et al. v. FIELDS \net al.", level=1),
            _text("body text"),
        ]
    )
    body_chunk = next(c for c in chunks if c.content_type == "text")
    assert body_chunk.section == "GOLDEY, ASSOCIATE WARDEN, et al. v. FIELDS et al."
    assert "\n" not in body_chunk.section


def test_bare_number_parent_stays_in_the_breadcrumb_above_its_dotted_children():
    """Found on a real arXiv paper: "3 Model Architecture" vanished from
    every breadcrumb below it (`Abstract > 3.1 Encoder...`) because its
    dotted child was given the same level and evicted it."""
    chunks = _build(
        [
            _heading("1 Introduction", level=2),
            _heading("3 Model Architecture", level=2),
            _heading("3.1 Encoder and Decoder Stacks", level=2),
            _text("body"),
        ]
    )
    body = next(c for c in chunks if c.content_type == "text")
    assert body.section == "3 Model Architecture > 3.1 Encoder and Decoder Stacks"


def test_same_size_headings_are_the_same_level_whatever_marker_said():
    """Found on a real 961-page book: every chapter heading is the same 14pt
    style, yet Marker gave them levels 1, 2, 3 and 4, nesting "CHAPTER IV"
    under "CHAPTER III"."""
    chunks = _build(
        [
            _heading("CHAPTER III", level=1, size=14.0),
            _heading("CHAPTER IV", level=4, size=14.0),
            _text("body"),
        ]
    )
    body = next(c for c in chunks if c.content_type == "text")
    assert body.section == "CHAPTER IV"


def test_larger_font_size_ranks_shallower():
    chunks = _build(
        [
            _heading("Book Title", level=3, size=17.0),
            _heading("Section", level=1, size=12.0),
            _text("body"),
        ]
    )
    body = next(c for c in chunks if c.content_type == "text")
    assert body.section == "Book Title > Section"


def test_unreal_font_size_is_ignored_and_marker_level_is_the_fallback():
    """Real RFC, court-opinion and financial-letter PDFs report a font size
    of 1.0 for every span (the text matrix does the scaling) - no signal, so
    the size ranking must not run on it."""
    chunks = _build(
        [
            _heading("Title", level=1, size=1.0),
            _heading("Sub", level=2, size=1.0),
            _text("body"),
        ]
    )
    body = next(c for c in chunks if c.content_type == "text")
    assert body.section == "Title > Sub"


def test_same_size_headings_stay_siblings_after_a_jump_across_sizes():
    """Found on a real DOCX news digest: a large section heading, then a run
    of small same-size headings (city, article, city, article...). Clamping
    each to "one deeper than the last" staircased every one under the one
    before it. Same size means same level, whatever came in between."""
    chunks = _build(
        [
            _heading("Digest", level=1, size=26.7),
            _heading("NOVOSIBIRSK", level=3, size=13.3),
            _heading("Anthem planned", level=3, size=13.3),
            _heading("KEMEROVO", level=3, size=13.3),
            _text("body"),
        ]
    )
    body = next(c for c in chunks if c.content_type == "text")
    assert body.section == "Digest > KEMEROVO"
