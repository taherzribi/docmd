"""Image handling: gives RAG pipelines a single, predictable convention for
what to do with images instead of Marker's raw behavior (an `![](file.jpeg)`
reference plus a separate dict of image bytes that most callers have no
plumbing for at all).

Three modes (see docmd.config.ConvertConfig.image_mode):
  - "placeholder": no binary data anywhere. Each image reference becomes a
    short, consistent text placeholder - safe to embed/chunk, nothing to
    resolve.
  - "alt-text": images are written to disk next to the output and kept as
    real Markdown image links with guaranteed non-empty alt text.
  - "skip": the image reference is removed entirely, no placeholder either.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]*)\)")


def apply_image_handling(
    markdown: str,
    images: dict[str, Any],
    mode: str,
    output_dir: str | Path | None = None,
) -> str:
    counter = 0

    def _replace(match: re.Match[str]) -> str:
        nonlocal counter
        alt_text, ref = match.group(1), match.group(2)

        if not ref.strip():
            # `![]()` with no reference at all - real Marker output on some
            # scanned pages (an OCR'd region with no recoverable image data).
            # No mode should keep this: a placeholder/skip has nothing to
            # describe, and alt-text mode would otherwise emit a link to
            # nowhere (an empty href renders as a broken image for no
            # legitimate reason, since there was never a file to begin with).
            return ""

        filename = Path(ref).name

        if mode == "skip":
            return ""

        if mode == "placeholder":
            label = alt_text.strip() or "image"
            return f"*[{label} omitted]*"

        # mode == "alt-text"
        counter += 1
        image = images.get(filename)
        if image is not None and output_dir is not None:
            out_path = Path(output_dir) / filename
            out_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(out_path)
        final_alt = alt_text.strip() or f"Image {counter}"
        return f"![{final_alt}]({ref})"

    return _IMAGE_RE.sub(_replace, markdown)
