# docmd

**Convert PDFs, DOCX, and PPTX to clean, structure-preserving Markdown — from the CLI or a Python library.**

Built for feeding documents into LLM and RAG pipelines, where clean Markdown beats raw text extraction.

*(Published on PyPI as `docmd-cli` since `docmd` was already taken by an unrelated
package — the import (`import docmd`) and CLI command (`docmd convert ...`) are
unaffected.)*

```bash
pip install docmd-cli
docmd convert report.pdf
```

```python
from docmd import convert

markdown = convert("report.pdf")
print(markdown)
```

## Why docmd

Great open-source document-to-Markdown converters already exist (docmd is built on
[Marker](https://github.com/datalab-to/marker)). The problem isn't quality — it's that
running them yourself means a Python environment, several GB of RAM, ideally a GPU, and
a non-trivial setup process before you convert your first file.

`docmd` wraps that engine with sane defaults and adds real post-processing on top
(table cleanup, heading normalization) so the output is closer to what a RAG pipeline
actually wants, not just raw model output.

See [EVIDENCE.md](EVIDENCE.md) for the specific real documents, real defects, and
real fixes behind that claim — not a benchmark score, a log of verifiable before/after
examples with the commit and regression test for each one.

A hosted API (`POST` a file, get Markdown back, no local setup) is planned — see
[ARCHITECTURE.md](ARCHITECTURE.md). It is not live yet; this repo is the open-source
core, usable standalone today.

## What it handles

| Input | Output |
|---|---|
| PDF (text-based) | Markdown with preserved headings, lists, tables |
| PDF (scanned) | Markdown via OCR — bundled by Marker, free, but needs [one extra native binary](#ocr-and-equations-need-one-native-binary) |
| DOCX | Markdown with formatting preserved (`pip install docmd-cli[full]`) |
| PPTX | Markdown, one section per slide (`pip install docmd-cli[full]`) |

## Quickstart

**CLI**
```bash
pip install docmd-cli
docmd convert my-file.pdf -o output.md
```

**Python**
```python
from docmd import convert

# From a file path
markdown = convert("my-file.pdf")

# From bytes
with open("my-file.pdf", "rb") as f:
    markdown = convert(f.read(), filename="my-file.pdf")
```

## Installing DOCX/PPTX support

The base install (`pip install docmd-cli`) covers PDF only and stays lean. DOCX and
PPTX need Marker's own additional dependencies:

```bash
pip install "docmd-cli[full]"
```

DOCX/PPTX conversion also needs [weasyprint](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation)'s
native Pango/GObject/Cairo libraries, which `pip` cannot install for you:

```bash
# macOS
brew install pango

# Debian/Ubuntu (24.04 and older)
sudo apt-get install libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info

# Debian trixie (13) and newer: libgdk-pixbuf2.0-0 was renamed
sudo apt-get install libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 libffi-dev shared-mime-info
```

PDF conversion (the base install) does not need this.

## OCR and equations need one native binary

Found by testing docmd against a real scanned document, not documented anywhere
upstream at the time of writing: Marker's current OCR and equation-recognition model
is a vision-language model served through either `vllm` (GPU/Linux-oriented) or
[llama.cpp](https://github.com/ggml-org/llama.cpp)'s `llama-server` binary - there is
no plain-CPU/transformers fallback. `pip install docmd-cli` cannot provide either one,
since neither ships as a normal Python wheel.

This only matters for **scanned PDFs** (no embedded text layer) and PDFs with
**equations** - a normal text-layer PDF never touches this code path, and everything
else in this README works with just `pip install`.

```bash
# macOS / Linux with Homebrew
brew install llama.cpp

# No Homebrew: download a prebuilt binary directly, no package manager needed
# (pick the archive matching your OS/arch from the releases page)
curl -LO https://github.com/ggml-org/llama.cpp/releases/latest/download/llama-<version>-bin-macos-arm64.tar.gz
tar xzf llama-<version>-bin-macos-arm64.tar.gz
export LLAMA_CPP_BINARY=$PWD/llama-<version>/llama-server
```

Without it, converting a scanned PDF or one with equations raises a
`MissingSystemDependencyError` with these same instructions - not a raw stack trace.
First real OCR run also downloads the model's GGUF weights from Hugging Face
(a few GB), separate from the PyTorch weights Marker already downloaded.

**OCR output is not guaranteed reproducible run to run** - confirmed directly:
the same scanned file through the same code path twice produced different text.
This is architectural (concurrent batched inference under the hood), not a docmd
bug and not fixable by a config flag alone - see [CONTRACT.md](CONTRACT.md) for the
full investigation. Doesn't affect plain text-layer PDFs, only pages that actually
go through OCR or equation recognition.

## Image handling

Images default to a text placeholder (`*[... omitted]*`) - no binary data, nothing to
resolve, safe for RAG chunking:

```python
markdown = convert("report.pdf")  # image_mode="placeholder" by default
```

To keep real image links instead, use `image_mode="alt-text"` and pass `output_dir` so
the image files actually get saved somewhere the links can resolve to:

```python
from docmd import convert_document
from docmd.config import ConvertConfig

result = convert_document(
    "report.pdf",
    config=ConvertConfig(image_mode="alt-text"),
    output_dir="output/",
)
```

From the CLI, `--image-dir` defaults to the output file's directory when `-o` is given:

```bash
docmd convert report.pdf -o output/report.md --image-mode alt-text
```

`image_mode="skip"` drops images entirely - no placeholder, no files.

## Provenance

Every conversion carries tracking info in `result.provenance` - useful for "this
converted differently yesterday" debugging:

```python
from docmd import convert_document

result = convert_document("report.pdf")
print(result.provenance)
# {'docmd_version': '0.1.3', 'backend': 'marker', 'backend_version': '2.0.0',
#  'ocr_used': False, 'conversion_duration_ms': 489}
```

Same shape regardless of which backend actually ran - `convert()` (the plain
string-returning function) doesn't expose this; use `convert_document()` for it.

## RAG-ready chunks

For search/RAG use cases that need more than one Markdown string, opt into
per-block chunks with page, section, content type, and bounding-box metadata:

```python
from docmd import convert_document
from docmd.config import ConvertConfig

result = convert_document("report.pdf", config=ConvertConfig(include_chunks=True))
for chunk in result.chunks:
    print(chunk.page, chunk.content_type, chunk.section, chunk.text[:50])
```

Or from the CLI: `docmd convert report.pdf --format rag -o chunks.json`.

One chunk per structural block the backend identified (a paragraph, a table, a
heading, an image, ...) by default. `content_type` is one of a small, stable
set (`text`, `heading`, `table`, `image`, `list`), independent of Marker's own
internal block-type names. `section` is a breadcrumb of the nearest heading at
each level above the chunk (e.g. `"Chapter 3 > 3.1 Introduction"`). Chunk text
is the block's own raw text, extracted before docmd's Markdown post-processing
runs - a table chunk's text is the backend's flattened cell text, not a
cleaned Markdown table. `chunks` is `None` unless `include_chunks=True` - the
default `convert_document()` call is unaffected.

Raw blocks are often too small (a bare heading, a one-sentence paragraph) or
too large (a big table) for good embeddings. Set `chunk_max_tokens` to merge
adjacent text/heading chunks - same page, same section - up to roughly that
many tokens (a cheap ~4-chars/token estimate, not a real tokenizer):

```python
config = ConvertConfig(include_chunks=True, chunk_max_tokens=400)
```

Tables, images, and lists are never merged into surrounding text, and merging
never crosses a page or section boundary. From the CLI:
`docmd convert report.pdf --format rag --chunk-max-tokens 400 -o chunks.json`.

## Extracting tables as CSV

Independent of the Markdown output, pull every table out of a document as its
own CSV file:

```
docmd extract report.pdf --tables csv -o tables/
# wrote 3 table(s) to tables/  (table_1.csv, table_2.csv, table_3.csv)
```

Markdown's backslash-escaping (e.g. `\$ 5,428`, so a dollar figure isn't read
as a math delimiter) is undone in the CSV output - that escaping is correct
in Markdown but meaningless once re-purposed as CSV.

## Validating the output

```
docmd validate report.pdf
✓ 12 heading(s) detected, no level skips
✓ 3 table(s), all consistent column counts
```

Reports concrete, verifiable findings about the converted document - never an
invented quality percentage, since docmd has no ground truth to back one up
with. Exits non-zero if anything is flagged (`⚠`), so it's usable as a CI
gate on your own document pipeline. The checks are the same ones that guard
docmd's own contract - see `CONTRACT.md` and `docmd/validate.py`.

## How it works

`docmd` wraps [Marker](https://github.com/datalab-to/marker) with sane defaults and a
clean output format, then runs its own post-processing pass
(`docmd/postprocess/`) to fix table structure and normalize heading levels — see
[ARCHITECTURE.md](ARCHITECTURE.md) for why this is the actual differentiation, not
just a thin wrapper, and [CONTRACT.md](CONTRACT.md) for exactly what's guaranteed
about the output (and what isn't, yet) — independent of Marker or any future backend.

## License

The `docmd` wrapper code is MIT — see [LICENSE](LICENSE).

`docmd` depends on [Marker](https://github.com/datalab-to/marker), whose code and
model weights carry *separate* licenses — the weights license has a revenue/funding
threshold that matters if you deploy commercially at scale. See
[docs/licensing.md](docs/licensing.md) for the precise terms; don't rely on this
sentence alone.

## Roadmap

- [x] PDF, DOCX, PPTX → Markdown
- [x] Table cleanup / heading normalization post-processing
- [ ] Hosted API
- [ ] OCR quality tuning for scanned documents
- [ ] Batch conversion endpoint
- [ ] HTML output option

## Contributing

Issues and PRs welcome. If you're hitting a conversion quality issue, please include a
sample file (or a minimal reproduction) — it makes fixes much faster.

---

*If docmd saves you the trouble of setting up your own PDF-parsing pipeline, consider starring the repo — it's how other people find it.*
