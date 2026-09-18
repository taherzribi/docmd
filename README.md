# docmd

**Convert PDFs, DOCX, and PPTX to clean, structure-preserving Markdown — from the CLI or a Python library.**

Built for feeding documents into LLM and RAG pipelines, where clean Markdown beats raw text extraction.

```bash
pip install docmd
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
| PDF (scanned) | Markdown via OCR — bundled by Marker, free |
| DOCX | Markdown with formatting preserved (`pip install docmd[full]`) |
| PPTX | Markdown, one section per slide (`pip install docmd[full]`) |

## Quickstart

**CLI**
```bash
pip install docmd
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

The base install (`pip install docmd`) covers PDF only and stays lean. DOCX and PPTX
need Marker's own additional dependencies:

```bash
pip install "docmd[full]"
```

DOCX/PPTX conversion also needs [weasyprint](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation)'s
native Pango/GObject/Cairo libraries, which `pip` cannot install for you:

```bash
# macOS
brew install pango

# Debian/Ubuntu
sudo apt-get install libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info
```

PDF conversion (the base install) does not need this.

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
