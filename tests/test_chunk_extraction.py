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
class _Block:
    block_type: _BlockType
    text: str
    page_id: int
    heading_level: int | None = None
    ignore_for_output: bool = False
    polygon: _Polygon = field(default_factory=_Polygon)

    def raw_text(self, _document):
        return self.text


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


def _heading(text, level):
    return _Block(block_type=_BlockType("SectionHeader"), text=text, page_id=0, heading_level=level)


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
