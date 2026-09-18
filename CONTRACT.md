# The docmd contract

This is what docmd guarantees about its output, independent of which extraction
backend is running underneath (currently [Marker](https://github.com/datalab-to/marker),
pinned to `marker-pdf==2.0.0`) or which platform it runs on. Everything here is
enforced by a test that fails if the guarantee breaks - the file is named next to
each one.

The reason this document exists: a test suite that asserts *the backend's exact raw
output* is testing the backend, not docmd, and breaks the moment the backend changes
- confirmed the hard way twice in this project's history (`066fd1b`, `c7225c5`), where
a test pinned an exact heading level Marker happened to produce on one platform, and
CI failed on a different platform running the identical, pinned backend version. Both
fixes replaced "assert the backend did X" with "assert docmd guarantees Y" - that
distinction is the entire point of this document.

## What's guaranteed

**Heading hierarchy** (`docmd/postprocess/heading_normalize.py`,
`tests/test_postprocess.py`, `tests/test_postprocess_more_integration.py`)
- No heading level skips more than one deeper than the deepest level seen so far.
  `H1` followed directly by `H4` becomes `H1` followed by `H2`; a later, legitimately
  deep heading elsewhere in the same document is left alone once the hierarchy has
  caught up. Confirmed against six independent real documents (an IMF report, four
  arXiv papers/patents, one hand-built fixture) - this is the single most common
  real-world defect found in this project's testing.
- No orphaned `#` with empty text.
- No heading whose text exactly repeats the immediately preceding heading (a Marker
  artifact from running page headers).
- A document's first heading is always promoted to H1 if nothing shallower precedes it.

**Table structure** (`docmd/postprocess/table_cleanup.py`)
- Every row in a rendered table has the same column count as its header, padded or
  truncated as needed.
- A missing or malformed separator row is synthesized.
- A stray row that is itself separator-shaped (all dashes) is dropped rather than
  rendered as literal data - found via a real two-column paper where a numbered
  equation came back as a one-row table with two separator rows.
- A table split into two blocks by a page break, with a repeated identical header, is
  merged into one continuous table.
- **Not guaranteed**: correct table content when the backend's own reading order is
  wrong. docmd normalizes structure; it doesn't re-derive reading order the backend
  got wrong (confirmed real gap: a patent's front-page bibliographic table).

**Image references** (`docmd/postprocess/image_handling.py`)
- No malformed Markdown image syntax (`![]()`  with an empty or partial reference)
  ever appears in output, in any mode.
- Three modes, each with a specific, tested behavior: `placeholder` (default, no
  binary data referenced at all), `alt-text` (real links, non-empty alt text, and the
  image file is actually written to `output_dir` if given), `skip` (removed entirely).

**Errors** (`docmd/errors.py`)
- A small, fixed set of `DocmdError` subclasses for known failure categories:
  `UnsupportedFormatError`, `MissingExtraError`, `MissingSystemDependencyError`,
  `EncryptedDocumentError`, `ConversionError`. Each carries an actionable message,
  not a raw backend stack trace, for the failure modes docmd knows about.

**Backend variation**
- Platform or backend-version differences in raw extraction output never change
  docmd's own guarantees above. They may change the *content* extracted (a backend
  bug is still a backend bug), but never the *structural* invariants this document
  lists.

**Provenance** (`docmd/converters/base.py:ConversionResult.provenance`)
- Every `convert_document()` call returns `docmd_version`, `backend`,
  `backend_version`, `ocr_used`, and `conversion_duration_ms` - same shape regardless
  of which backend ran.

## What's explicitly not guaranteed (yet)

Found by real-world testing, not fixed:

- **Form/checkbox structure.** Adjacent checkbox option labels (e.g. a tax form's
  filing-status options) are not separated or structured - they extract as one
  run-on phrase, identical to raw backend output.
- **RTL bidirectional punctuation.** Citation brackets and similar LTR punctuation
  embedded in right-to-left script can render reversed (`]1[` instead of `[1]`).
- **Multi-column reading order in dense bibliographic/legal layouts.** Proven to
  work correctly on a two-column academic paper; proven to fail on a patent's
  front-page citation block. No known rule yet for which case a given document falls
  into.

## Writing a new test against this contract

Ask: does this assertion describe something docmd promises, or something the
backend happened to do on one machine? If the latter, either don't assert it, or -
if it's worth pinning as a canary for upstream behavior changing silently - say so
explicitly in the test's docstring and keep it separate from the real assertion, the
way `test_marker_really_does_split_a_page_spanning_table` and
`test_running_header_does_not_leak_into_output` do.
