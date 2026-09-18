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

## How it works

`docmd` wraps [Marker](https://github.com/datalab-to/marker) with sane defaults and a
clean output format, then runs its own post-processing pass
(`docmd/postprocess/`) to fix table structure and normalize heading levels — see
[ARCHITECTURE.md](ARCHITECTURE.md) for why this is the actual differentiation, not
just a thin wrapper.

## License

The `docmd` wrapper code is MIT — see [LICENSE](LICENSE).

`docmd` depends on [Marker](https://github.com/datalab-to/marker), whose *code* is
Apache-2.0 and whose *model weights* are licensed under a modified Open RAIL-M license:
free for research, personal use, and organizations under $5M in funding or revenue.
Commercial use beyond that threshold requires a license from
[Datalab](https://www.datalab.to/pricing). This applies to you if you deploy `docmd`
commercially at scale — check Marker's current license terms directly before doing so.

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
