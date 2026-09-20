# Real bugs, real documents

This page is for anyone deciding whether docmd is worth using over raw
[Marker](https://github.com/datalab-to/marker). It is not a benchmark with
accuracy percentages — see [CONTRACT.md](CONTRACT.md) for why: docmd wraps
Marker rather than replacing it, so a number like "text accuracy: 97%" would
mostly be measuring Marker, not docmd, and would need ground-truth
annotation this project doesn't have. What follows instead is a log of
specific, verifiable claims: real documents, the defect each one exposed in
raw Marker output, the fix, and the commit and regression test that prove
it. Every example below can be reproduced from the commit referenced.

This project has also verified several claims it *didn't* have to fix
because they turned out to already work, and documents two real gaps it
found but couldn't fix well — both included below, on the theory that a
page that only shows wins isn't trustworthy.

## Bugs found and fixed

### A repeated running header, misclassified as a heading

**Found on:** a real 27-page IMF report, and a synthetic reproduction
(`tests/fixtures/running_header.pdf`).

Marker's raw output on some platforms assigned the running header
"CONFIDENTIAL - INTERNAL REPORT" its own heading level, and jumped between
inconsistent heading depths for structurally identical sections — `H1` to
`H4` with nothing in between, or the same section header rendered at `H2` on
one run and `H3` on another. This was the single most common real-world
defect found across six independent documents.

**Fix:** `docmd/postprocess/heading_normalize.py` clamps any level-skip to at
most one deeper than the deepest level already seen, drops a heading that
exactly repeats the one before it, and promotes an unstyled first heading to
`H1`. Commit `b84ee46`, hardened for cross-platform variance in `066fd1b`.

### A numbered equation rendered as a broken one-row table

**Found on:** "Attention Is All You Need" (a real two-column academic
paper).

A numbered equation came back from Marker as a one-cell "table" with two
separator rows back to back and no real data row - the second separator
rendered as a literal row of dashes in the final Markdown:

```
| Attention(Q, K, V) = softmax(...)V | (1) |
|----------------------------------------|-----|
|----------------------------------------|-----|
```

**Fix:** `docmd/postprocess/table_cleanup.py` drops any row that is itself
separator-shaped rather than treating it as data. Commit `c7225c5`.

### A multiprocessing crash on any sufficiently large PDF

**Found on:** a real arXiv paper, long enough to trigger Marker's default
4-worker `ProcessPoolExecutor` for page-text extraction.

On macOS and Windows (spawn-based multiprocessing), this crashed with `An
attempt has been made to start a new process before the current process has
finished its bootstrapping phase` for any caller not wrapped in
`if __name__ == "__main__":` - an easy trap for a library used from a
script, notebook, or web server request handler. Small test fixtures never
hit this, since it only appears on sufficiently multi-page documents.

**Fix:** docmd pins `pdftext_workers=1`, trading a little extraction
parallelism for not crashing on arbitrary callers. Commit `7abd954`.

### A missing OCR dependency with no clear error

**Found on:** a real scanned PDF downloaded from archive.org.

Marker's OCR and equation recognition needs the `llama-server` binary from
llama.cpp, which isn't installable via pip. Without it, conversion of a
scanned document failed with a raw stack trace, not an explanation.

**Fix:** a dedicated `MissingSystemDependencyError` with install
instructions. Commit `7abd954`.

### Reversed citation brackets in right-to-left script

**Found on:** a real Arabic Wikipedia article (مصر / Egypt).

A citation link wrapped in brackets came out of extraction reversed - `]
[1](#page-21-0)[` instead of `[1](#page-21-0)` - a bidirectional-text
extraction artifact from Latin punctuation embedded in Arabic script.

**Fix:** `docmd/postprocess/rtl_fix.py` corrects the reversed span. Proven
safe rather than merely plausible: a correctly-ordered Markdown link can
never start with `]`, so the pattern this targets cannot occur in
legitimate content - verified against real prose containing normal adjacent
citations (`[1](#fn1)[2](#fn2)`), which pass through untouched. The
equivalent reversal in parentheses is deliberately left unfixed - see
Known limitations. Commit `274aba2`.

### Dot-leader filler leaking into table cells

**Found on:** a real Berkshire Hathaway shareholder letter's 59-year
performance table, a dot-leader-style table with no gridlines.

```
| 1965 ........................................................ | 49.5 |
```

**Fix:** `docmd/postprocess/table_cleanup.py` strips runs of 4+ dot-leader
characters from cell text (4+, not 3+, so a standard prose ellipsis is
never touched). Commit `a157f07`.

### Markdown escaping leaking into CSV export

**Found on:** the same Berkshire Hathaway letter's segment-earnings table.

A dollar figure correctly renders in Markdown as `\$ 5,428` (so a
Markdown/KaTeX renderer doesn't read `$` as a math delimiter) - but that
escaping is wrong once re-purposed as CSV via `docmd extract --tables csv`.

**Fix:** Markdown's backslash-escaping is undone specifically in the CSV
export path; the Markdown output itself is untouched. Commit `a157f07`.

### An empty image reference nothing could match

**Found on:** a real scanned PDF.

`![]()` with no href and no alt text, directly adjacent to a real image
reference with no separator, leaked through every image mode unprocessed -
the regex required at least one character inside the parens.

**Fix:** widened the match to allow a fully empty reference. Commit
`7abd954`.

### Wrong heading depth, in Markdown and in RAG breadcrumbs

**Found on:** RFC 9113, "Attention Is All You Need", and a 961-page real book, by
stress-testing chunks and search against nine real documents.

Marker infers heading depth from visual layout, and it is noisy. It gave
`5.4 Error Handling` the same level as the deeper `5.3.1`/`5.3.2` before it; gave
`1 Introduction` and `6 Results` different levels; let `3.1 Encoder...` evict its own
parent `3 Model Architecture` from the breadcrumb; and, in the book, gave four
different levels to chapter headings that are all one 14pt style, nesting "CHAPTER IV"
under "CHAPTER III". The existing skip-clamp couldn't catch any of it - none of these
are level skips, just wrong levels.

**Fix:** section numbers are used as relative structure (`docmd/heading_numbering.py`,
shared by the Markdown pass and chunk breadcrumbs), and chunk breadcrumbs rank
headings by font size where the PDF reports a real one. After: the arXiv paper's
outline and the RFC's, down to `6.5.3`, come out exactly right. Where a PDF reports a
font size of 1.0 for everything (this RFC, a court opinion, a financial letter) there
is no signal, and unnumbered headings still get Marker's noisy levels - documented in
[CONTRACT.md](CONTRACT.md), not hidden. Commits `0cc9513` and `a894685`.

### Search ranked a repetitive chunk above the one that defines the term

**Found on:** a real arXiv paper, querying "self-attention".

Ranking by raw word counts put a long bullet repeating "attention" ahead of the short
chunk that defines self-attention. **Fix:** BM25 (rare-term weighting, saturation, length
normalization). Commit `8fdb31d`.

### PowerPoint slides flowing together with no boundaries

**Found on:** six real decks from Apache POI's public test set, converted through
`docmd batch --format rag`.

34 slides came out as 15 "pages", 28 as 11, 24 as 7, 10 as 2, and nothing in the
Markdown or chunks marked where a slide began - so the README's "one section per slide"
was untrue. Marker has an `include_slide_number` option for exactly this, but it is dead
in marker-pdf 2.0.0: the slide HTML is built before the config is applied, so it can
never be enabled through config.

**Fix:** set on Marker's provider class directly. After, a real 9-slide deck produces
exactly 9 `Slide N` sections with titles nested beneath. The same test found and
documented (not fixed) three limits: speaker notes are dropped by Marker, WMF images
couldn't be decoded in testing on macOS, and `page` for Office files is a rendered-PDF page.
Text recall on all 14 real DOCX/PPTX files was 95-100%.

## Claims verified, not just assumed

- **Multi-column reading order.** A prior finding suggested this could fail
  on dense bibliographic layouts. Retested against five more real patents
  (1975-2021, both front-page bibliographic blocks and multi-column body
  text) and a 20-page excerpt of a genuinely 3-column Federal Register
  issue. All six read in correct order. Commit `cd707d0`.
- **Page rotation.** A real patent PDF with one page's `/Rotate` flag set to
  90 degrees converted byte-for-byte identical to the unrotated original.
  Commit `cd707d0`, regression-tested in `280cc6c`.
- **Large documents.** A 961-page, purely text-layer PDF converted
  completely and correctly - verified against the real source text - in
  under two minutes, at roughly 8GB peak memory, no crash or truncation.
  Commit `cd707d0`.
- **OCR non-determinism, root-caused, not guessed.** Running the identical
  scanned file through the identical code path twice produced different
  text (confirmed directly: 28,916 vs 27,973 characters on one real
  document). Traced through Surya's own source to a specific, verifiable
  cause: `llama-server` batches inference across 8 concurrent requests by
  default, and floating-point matrix multiplication under concurrent
  batching is not strictly order-independent - a documented property of
  every major LLM-serving stack, not a docmd or Marker bug. Documented in
  [CONTRACT.md](CONTRACT.md) rather than silently left unexplained.

## Known limitations, documented rather than hidden

- **Form/checkbox structure.** Confirmed against a real IRS W-4: Marker's
  layout model has no structural signal at all tying adjacent
  filing-status checkbox options together, and the checkbox glyphs
  themselves are vector graphics with no text-layer representation.
  Fixing this needs new capability (PDF form-field extraction), not a
  Markdown-level post-processing fix.
- **A table cell value extracted out of order.** Found via a real Chinese
  Wikipedia article: an infobox's "小儿经" (Xiao'erjing) value was
  extracted 18 lines away from its own label. Genuine content, not a
  hallucination - a backend reading-order defect outside what
  Markdown-string post-processing can reliably repair.

See [CONTRACT.md](CONTRACT.md) for the complete, current list of what
docmd guarantees and what it explicitly doesn't yet.

## Verify this yourself

Every fix above has a regression test in `tests/`, generated from
synthetic fixtures that reproduce the same structural defect the real
document exposed (real copyrighted documents aren't redistributed here -
see `tests/fixtures/generate_stress_fixtures.py`). Run `pytest`, or
`docmd validate <your own document>` against something you already have.
