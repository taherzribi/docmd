# Architecture: Doc-to-Markdown API

## The pitch (keep this pinned above your desk)
We are not competing on conversion quality. We are selling **"hit an endpoint, get clean Markdown back"** — no Python env, no 8GB+ RAM, no GPU, no dependency hell. The open-source core proves the engine works and builds trust. The hosted API sells convenience.

## Positioning risk (checked 2026-09-18)
Marker's *code* is Apache-2.0 (no restriction). Marker's *model weights* use a modified
Open RAIL-M license: free for research, personal use, and organizations under $5M in
funding/revenue; beyond that, a commercial license from Datalab is required. This is not
a launch blocker for a bootstrapped start, but it is a real ceiling to plan around if the
hosted API grows past that threshold. Separately, Datalab already runs its own hosted
"upload a file, get Markdown back" API (datalab.to/pricing) with a free tier and
pay-as-you-go pricing — so "convenience" alone is not a durable moat, since Datalab
already sells that. The real differentiator has to be the post-processing quality (see
below), not just "no setup required." Every feature that's free elsewhere (e.g. OCR,
which Marker already bundles) should stay free in `docmd` too; gating something users
can trivially get by calling Marker directly doesn't protect revenue, it just damages
trust.

---

## System overview

```
                        +---------------------------+
                        |   docmd (OSS library)      |  <- pip install docmd-cli
                        |   Python CLI + library     |  <- free, MIT license
                        |   wraps Marker under       |
                        |   the hood                 |
                        +--------------+--------------+
                                       | same core logic,
                                       | imported not duplicated
                                       v
+--------------+    +---------------------------+    +-----------------+
|   Client      |--->|   API Gateway (FastAPI)   |--->|  Inference       |
|  (curl, SDK,  |    |   - auth (API keys)       |    |  Worker (GPU)    |
|   your docs)  |    |   - rate limiting         |    |  Modal / RunPod  |
+--------------+    |   - usage metering         |    |  runs Marker     |
       ^             |   - job queue              |    +--------+---------+
       |             +--------------+--------------+             |
       |                            |                             |
       |                            v                             |
       |             +---------------------------+                |
       |             |  Postgres (Supabase)       |                |
       |             |  - users, api_keys         |<---------------+
       |             |  - usage_events            |   writes result +
       |             |  - jobs (status/result)    |   usage back
       |             +---------------------------+
       |                            ^
       |                            |
       |             +---------------------------+
       +------------>|  Stripe (billing)          |
      webhook events  |  - subscriptions            |
                       |  - usage-based invoicing   |
                       +---------------------------+
```

**Key architectural decision: the OSS library and the hosted API share the same core conversion code.** Put the actual conversion logic (file -> Markdown) in the open-source package. The API is a thin, closed-source wrapper around it that adds auth, billing, queuing, and GPU orchestration. This way:
- The OSS repo is genuinely useful standalone (real trust, real stars)
- You never duplicate logic between "free" and "paid"
- Improvements to the core benefit both

---

## Repo structure

This repo currently contains **Stage 1 only**: the `docmd/` OSS package. The `api/`
folder (hosted API) is a later stage, described below for context but not yet built.

```
docmd/
|-- README.md
|-- ARCHITECTURE.md
|-- LICENSE                       # MIT for the core package
|-- pyproject.toml                # package config for `docmd` on PyPI
|-- docmd/                        # --- OSS PACKAGE (public, pip-installable) ---
|   |-- __init__.py
|   |-- cli.py                    # `docmd convert file.pdf` entrypoint
|   |-- converters/
|   |   |-- __init__.py
|   |   |-- base.py               # Converter protocol/interface
|   |   |-- marker_converter.py   # wraps datalab-to/marker
|   |   `-- registry.py           # maps file type -> converter
|   |-- postprocess/              # THIS is where docmd earns its existence
|   |   |-- table_cleanup.py      # fix mangled table structure from raw Marker output
|   |   |-- heading_normalize.py  # consistent heading levels, no orphaned headers
|   |   `-- image_handling.py     # consistent alt-text / placeholder convention
|   |-- config.py
|   `-- errors.py                 # error taxonomy
|-- tests/
|   |-- test_cli.py
|   |-- test_converters.py
|   |-- test_postprocess.py
|   `-- fixtures/                 # sample pdf/docx test files (generated)
`-- .github/
    `-- workflows/
        `-- ci.yml                 # tests on PR

# Not yet built (later stage):
# api/            - FastAPI hosted service (auth, billing, queue, GPU worker)
```

### Post-processing: the actual product
Raw Marker output is good but not perfect for RAG use — this is where `docmd` needs to add real value instead of being pure plumbing:
- **Table cleanup**: fix structure that comes out mangled from complex layouts
- **Heading normalization**: consistent heading levels, no orphaned/duplicate headers
- **Image handling**: a consistent convention for alt-text or placeholders (RAG pipelines need to know what to do with images, even if just "skip")
- **Optional LLM polish pass** (v2, opt-in, costs extra): run a cheap LLM call over the output to fix remaining formatting oddities — this is a legitimate premium feature since it has a real marginal cost

Treat this folder as the actual differentiator. A thin wrapper is a weekend project; good post-processing is a product.

---

## Tech stack (with reasoning)

| Layer | Choice | Why |
|---|---|---|
| OSS core | Python, wraps `marker-pdf` (pinned `==2.0.0`) | Don't reinvent conversion; Marker has ~40k combined stars (with Surya) and active maintenance |
| API framework (later stage) | FastAPI | Async-friendly, great for I/O-bound job queuing, auto-generates OpenAPI docs |
| GPU inference (later stage) | Modal (first choice) or RunPod | Modal has better Python DX and publishes an official Marker deployment guide; RunPod is often cheaper at scale |
| Database (later stage) | Postgres via Supabase | Free tier is generous, easy to self-host later |
| Billing (later stage) | Stripe, prepaid credits by default | Avoids surprise invoices |
| API deploy (later stage) | Railway or Fly.io | Simple deploys, no k8s complexity |

---

## Packaging: optional dependencies

- `pip install docmd-cli` -> core PDF conversion (Marker bundles OCR here already; there is
  no separate lean/no-OCR base install, since Marker's own base dependencies include
  `surya-ocr`)
- `pip install docmd-cli[full]` -> adds DOCX/PPTX/EPUB/XLSX support via Marker's `full` extra

## License clarity

MIT for the `docmd` wrapper is fine and expected for an OSS trust play. Marker's code is
Apache-2.0. Marker's *model weights* are under a modified Open RAIL-M license: free for
research, personal use, and organizations under $5M funding/revenue; beyond that, a paid
license from Datalab is required (see datalab.to/pricing). Re-check this before scaling
the hosted API past that threshold.

## What "done" looks like for Stage 1 (this repo, today)

- [x] `docmd` installable via `pip install -e .` locally
- [x] Converts a PDF to Markdown from the CLI in one command
- [x] Post-processing (table cleanup, heading normalization) visibly improves on raw Marker output
- [x] README has a compelling before/after example and a 30-second quickstart
- [ ] Published to PyPI
- [ ] Hosted API (later stage, not built yet)
