"""Conversion configuration for docmd.

Kept small and explicit. This is *not* the hosted API's config (rate limits,
billing thresholds, etc.) - see ARCHITECTURE.md, that lives in `api/` in a
later stage. This is just what controls a single conversion.
"""

from __future__ import annotations

from dataclasses import dataclass

_VALID_IMAGE_MODES = {"placeholder", "alt-text", "skip"}


@dataclass
class ConvertConfig:
    """Options for a single conversion.

    Attributes:
        use_llm: Ask Marker to use an LLM pass for higher-fidelity extraction
            of tricky tables/forms. Off by default: it requires an API key
            for an LLM provider and has a real marginal cost, so it should be
            an explicit opt-in rather than a surprise dependency.
        force_ocr: Force OCR even on PDFs that already have a text layer.
            Useful for PDFs with a broken/garbled embedded text layer.
        normalize_headings: Run docmd's own heading-normalization
            post-processing pass (see postprocess/heading_normalize.py).
        clean_tables: Run docmd's own table-cleanup post-processing pass
            (see postprocess/table_cleanup.py).
        image_mode: How to represent images in the output Markdown.
            - "placeholder" (default): RAG-friendly. No binary image data is
              written; each image becomes a short, consistent placeholder
              line so downstream chunking/embedding code has something
              predictable to key off (or skip) rather than a dangling link.
            - "alt-text": images are saved next to the output file and kept
              as real Markdown image links with non-empty alt text.
            - "skip": images are dropped entirely, no placeholder either.
    """

    use_llm: bool = False
    force_ocr: bool = False
    normalize_headings: bool = True
    clean_tables: bool = True
    image_mode: str = "placeholder"

    def __post_init__(self) -> None:
        if self.image_mode not in _VALID_IMAGE_MODES:
            raise ValueError(
                f"image_mode must be one of {sorted(_VALID_IMAGE_MODES)}, "
                f"got {self.image_mode!r}"
            )
