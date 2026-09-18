# Licensing

Three separate things, three separate licenses. Conflating them is the exact
overclaim this document exists to prevent.

## docmd itself

MIT - see [LICENSE](../LICENSE). No restrictions on commercial use, modification, or
redistribution of docmd's own wrapper/post-processing code.

## Marker's source code

docmd depends on [Marker](https://github.com/datalab-to/marker), pinned to
`marker-pdf==2.0.0`. Marker's code is Apache-2.0. No restriction relevant here.

## Marker's model weights

This is the one that actually constrains you, and it's separate from the code
license above - a common point of confusion, and the reason this file exists rather
than a single blanket "Marker is Apache-2.0" statement.

Marker's model weights (the actual OCR/layout/recognition models, downloaded
separately from the code) are licensed under a **modified Open RAIL-M license**:

- Free for research, personal use, and organizations under **$5M in funding or
  revenue**.
- Beyond that threshold, a commercial license from [Datalab](https://www.datalab.to/pricing)
  (Marker's maintainer) is required.

**This applies to you if** you deploy docmd commercially at a scale that crosses that
threshold - not at small/bootstrapped scale, but worth planning around before it
matters. Check Marker's current license terms directly before relying on this
summary; license terms can change between versions, and the terms above reflect
`marker-pdf==2.0.0` specifically, checked 2026-09-18.

**If you're building a hosted/SaaS product on top of docmd**: Datalab runs its own
hosted document-conversion API. Before launching a commercial hosted API built on
Marker, get written clarification from Datalab on whether your product would be
considered competitive with theirs under their weights license - don't assume the
$5M threshold is the only relevant term. This is a business/legal step, not
something resolvable by reading the license text alone.

## Other dependencies

docmd's `[full]` extra and the OCR/equation path pull in several other open-source
projects (`weasyprint`, `python-docx`, `python-pptx`, `llama.cpp`, and Marker's own
transitive dependencies). None of these are known to impose restrictions beyond their
standard OSS licenses (BSD/MIT/Apache-family) as of this writing, but this file
doesn't audit them individually - check `pyproject.toml` for the current pinned
versions if you need to.
