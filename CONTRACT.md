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

`tests/test_benchmark.py` runs every guarantee below against the *whole* fixture
corpus at once - a scorecard, not a percentage score - so a regression in any one
fixture gets caught even if it isn't the fixture that originally found the bug.

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
- A heading with its own visible dotted-decimal numbering (`5.4`, `5.4.1`) is leveled
  by that numbering, not by Marker's own visually-inferred level, when the two
  disagree. Found via two independent real documents - RFC 9113 and "Attention Is All
  You Need" - where Marker assigned a heading (`5.4 Error Handling`, `3.3
  Position-wise Feed-Forward Networks`) the *same* level as the deeper sibling right
  before it (`5.3.1`/`5.3.2`, `3.2.1`/`3.2.2`/`3.2.3`), nesting it one level too deep
  instead of alongside its true siblings. Not a level *skip* - the skip-clamp above
  doesn't catch it, since the wrong level was still reachable. Requires at least one
  embedded dot (two-plus numbering segments), so a heading merely starting with a bare
  number (`2024 Outlook`) - too ambiguous a signal for nesting depth - never triggers
  this override. Applies identically to RAG chunk section breadcrumbs (see
  `docmd/converters/chunk_extraction.py`) - confirmed both outputs had the identical
  defect on both real documents before this fix, not something unique to one path.
- **Not guaranteed**: correct depth for headings using a different numbering
  convention than dotted-decimal (Roman numerals, "Chapter N", bare sequential
  numbers). Found via a 961-page real book: Marker assigned wildly inconsistent
  levels (1 or 4) to "CHAPTER I" through "CHAPTER XII" despite them being visually
  identical, produced by the exact same styling - evidence that Marker's
  heading-level signal is noisy in general, not just for one numbering convention.
  No safe, general text pattern was found to correct this without risking false
  positives on unrelated content.

**Table structure** (`docmd/postprocess/table_cleanup.py`)
- Every row in a rendered table has the same column count as its header, padded or
  truncated as needed.
- A missing or malformed separator row is synthesized.
- A stray row that is itself separator-shaped (all dashes) is dropped rather than
  rendered as literal data - found via a real two-column paper where a numbered
  equation came back as a one-row table with two separator rows.
- A table split into two blocks by a page break, with a repeated identical header, is
  merged into one continuous table.
- A run of 4+ dot-leader characters (`....` or `. . . .`, the visual filler between a
  label and its value in dot-leader-style tables with no gridlines) is stripped from
  cell text - found via a real Berkshire Hathaway shareholder letter's performance
  table. A standard 3-dot prose ellipsis is never touched.
- **Not guaranteed**: correct table content when the backend's own reading order is
  wrong. docmd normalizes structure; it doesn't re-derive reading order the backend
  got wrong (confirmed real gap: a patent's front-page bibliographic table).

**CSV table export** (`docmd/tables.py`, `docmd extract file --tables csv`)
- Operates on the already-cleaned Markdown (after `clean_tables` has run), so every
  table it exports is already structurally consistent.
- Markdown's backslash-escaping of punctuation (e.g. `\$`, `\*`) is undone - correct
  in Markdown, meaningless once re-purposed as CSV. Found via the same Berkshire
  Hathaway letter: a segment-earnings table's dollar figures rendered as `\$ 5,428`.

**Validation** (`docmd/validate.py`, `docmd validate file`)
- Every finding is a concrete, verifiable structural fact - never a numeric quality
  score, since docmd has no ground truth to compute one honestly against.
- Runs the identical checks `tests/test_benchmark.py` runs against the whole fixture
  corpus (same functions, imported not duplicated) - if a document a user converts
  triggers a warning, that's either a genuine new gap or the same class of thing
  CONTRACT.md's own history was built from finding.

**Image references** (`docmd/postprocess/image_handling.py`)
- No malformed Markdown image syntax (`![]()`  with an empty or partial reference)
  ever appears in output, in any mode.
- Three modes, each with a specific, tested behavior: `placeholder` (default, no
  binary data referenced at all), `alt-text` (real links, non-empty alt text, and the
  image file is actually written to `output_dir` if given), `skip` (removed entirely).

**RTL citation brackets** (`docmd/postprocess/rtl_fix.py`)
- A reversed `]...[` citation-bracket span (from bidirectional-text extraction of
  LTR punctuation embedded in RTL script) is always corrected to `[...]`. Does not
  cover the equivalent reversal for parentheses - see "What's explicitly not
  guaranteed" below.

**RAG chunks** (`docmd/converters/chunk_extraction.py`, opt-in via
`ConvertConfig.include_chunks`)
- `content_type` is always one of `docmd.converters.base.CONTENT_TYPES` - never a raw
  Marker block-type name.
- A page header/footer repeated across pages (including the case where it gets
  misclassified as a heading on a later page - the same real defect
  `heading_normalize.py` guards against at the Markdown-string level) never produces
  its own chunk.
- Chunk text is the backend's own raw per-block text - it does not receive
  `clean_tables`, `heading_normalize`, or `fix_rtl_brackets`'s fixes, since those
  operate on the final rendered Markdown string, not individual blocks.
- `chunks` is `None` (not an empty list) unless `include_chunks=True` was passed.

**Chunk merging** (`docmd/converters/chunk_merge.py`, opt-in via
`ConvertConfig.chunk_max_tokens`)
- A `table`, `image`, or `list` chunk is never merged into surrounding text, and
  merging never crosses a page or section boundary - checked directly, not just
  implied by the token budget.
- A single chunk already at or over the token budget is emitted on its own rather
  than split - this does not attempt to break up an oversized block.
- Token count is a `len(text) // 4` estimate, not a real tokenizer - don't build
  exact-token-count behavior on top of it.

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
  of which backend ran. This records *what ran*, not that the *output* is
  reproducible - see OCR determinism below, where it isn't.

## What's explicitly not guaranteed (yet)

Found by real-world testing, not fixed:

- **Form/checkbox structure.** Confirmed against a real IRS W-4: Marker's layout
  model does detect a `Form` block type (visible in `page_stats.block_counts`), so
  it isn't invisible to the pipeline - but Marker renders `Form` blocks as flattened
  prose, not a table or option list, and checkbox squares are vector graphics with
  no text-layer representation at all, so nothing marks three filing-status options
  as mutually-exclusive choices. Fixing this means operating on Marker's block tree
  before it renders to Markdown - a real architecture change (docmd's post-processing
  today only ever touches the already-rendered Markdown string), not a bounded fix.
- **RTL bidirectional punctuation - square brackets fixed, parentheses not.** Found
  via a real Arabic Wikipedia article: citation brackets wrapping a footnote link
  came out reversed (`][1](#page-21-0)[` instead of `[1](#page-21-0)`), a bidirectional
  text-extraction artifact from LTR punctuation embedded in RTL script. Fixed for
  square brackets in `docmd/postprocess/rtl_fix.py` - safe because a correctly-ordered
  Markdown link or reference can never start with `]`, so every `]...[` span is
  unambiguously this artifact, never legitimate content. The same reversal affects
  parentheses (`)6,000 km2(` instead of `(6,000 km2)`), left unfixed: normal prose
  legitimately places two independent parentheticals back to back - "word (first) and
  (second)" - which a naive `)...( -> (...)` swap would corrupt, and there's no
  Markdown-syntax signal (like brackets have) to tell the two cases apart.
- **Multi-column reading order in dense bibliographic/legal layouts.** Proven to
  fail once, on a patent's front-page citation block (that specific PDF wasn't kept
  as a fixture, per the policy against redistributing real-world documents, so it
  can't be re-run directly). Re-tested since against six more real documents - five
  more patents spanning 1975-2021 (both front-page bibliographic blocks and
  multi-column body text) and a 20-page excerpt of a genuinely 3-column Federal
  Register issue - and all six read in correct order. The failure is real but appears
  to be narrow or document-specific rather than a general multi-column defect; no
  reproduction means no fix to make yet.
- **Table/infobox cell dissociation.** Found via a real Chinese Wikipedia article
  (中國): a sidebar infobox's "小儿经" (Xiao'erjing - Mandarin written in Arabic
  script) row had its label and value extracted as two separate, disconnected
  fragments - the value landed 18 lines earlier in the document, before the infobox
  it belongs to even starts. Not a hallucination (the Arabic-script text is genuine
  content, correctly recognized) - the backend's reading order detached a table
  cell's value from its own row. A layout-detection issue in the backend, not
  something docmd's structural post-processing (which operates on already-rendered
  Markdown, not layout geometry) can reliably repair.
- **Page rotation: not a gap, but the first regression test for it broke CI.** A real
  patent PDF with one page's `/Rotate` flag set to 90deg converted byte-for-byte
  identical to the unrotated original on this machine - rotation itself is handled
  transparently. The first synthetic fixture for this (one bare sentence per page)
  passed locally but failed in Linux CI: the layout model classified the rotated
  page's lone short line as a `PageFooter` (which Marker excludes from output)
  instead of body text, a borderline call that differed by platform - the same
  backend-non-determinism class as the OCR entry below, just in the layout model
  instead of the recognition model, and the third time this exact category of test
  has broken CI in this project's history. Fixed by giving the fixture a full
  paragraph per page instead of a single line, which stays clear of that
  classification boundary. See `tests/test_postprocess_more_integration.py`.
- **Large documents (500+ pages): not a gap.** A 961-page, purely text-layer PDF (no
  OCR involved) converted completely and correctly - verified start and end content
  against the real source text - in under two minutes, with peak memory around 8GB.
  No crash, no truncation. Worth knowing for capacity planning (e.g. `docmd-api`'s
  container memory limits) even though it isn't a defect.
- **OCR reproducibility.** Running the identical file through the identical code path
  twice, in the same process, produced different text - confirmed directly, not
  inferred (28,916 vs 27,973 characters on a real degraded scan; individual word
  choices and even a poem's line-break structure differed between the two runs).
  Root cause investigated and is architectural, not a misconfiguration: OCR/equation
  recognition already requests greedy decoding (`temperature=0.0`, confirmed in
  `surya/inference/backends/openai_client.py`), but `llama-server` runs with
  `--parallel 8` by default (`surya/inference/backends/llamacpp.py`), and
  floating-point matrix multiplication under concurrent batched inference is not
  strictly order-independent - a well-documented property of essentially every
  production LLM-serving stack (vLLM, llama.cpp, TensorRT-LLM), not specific to this
  one. A small numerical difference from batch composition can flip an argmax choice
  at a near-tied token, and the autoregressive generation diverges from there.
  `SURYA_INFERENCE_PARALLEL=1` (env var, not currently exposed through docmd's own
  config) would remove the batching-composition variable and likely reduce this a
  lot, at a real throughput cost - untested, and even then, multi-threaded CPU matrix
  math without an explicit `--threads 1` could still leave some residual variance.
  Does not affect the plain `pdftext` text-extraction path (no VLM inference
  involved) - only pages that actually go through OCR or equation recognition.

## Writing a new test against this contract

Ask: does this assertion describe something docmd promises, or something the
backend happened to do on one machine? If the latter, either don't assert it, or -
if it's worth pinning as a canary for upstream behavior changing silently - say so
explicitly in the test's docstring and keep it separate from the real assertion, the
way `test_marker_really_does_split_a_page_spanning_table` and
`test_running_header_does_not_leak_into_output` do.
