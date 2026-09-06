# Lauudit — Legal-AI citation auditor with live Singapore judgment verification

Lauudit is a local Chrome Manifest V3 extension and FastAPI service for
auditing citations in rendered legal-AI answers. The browser captures the
answer as structured text/Markdown with links and offsets, the backend extracts
and verifies citations, and the side panel shows citation-level findings. Live
verification is enabled by default: official eLitigation resolution is the
source of truth for citation authenticity in the MVP. No cloud database or
external LLM API is required at runtime.

## Problem statement progress

- [x] **Hallucination: catch fake cases.** The citation-authenticity MVP
  combines deterministic extraction with official eLitigation search and direct
  metadata matching to detect fabricated, mismatched, and unresolvable
  citations. This does not prove that a legal proposition is correct.
- [x] **Contextual accuracy: understand why a case matters.**
  The `llm_judge` evaluator classifies a retrieved paragraph as ratio, obiter,
  overgeneralized, contradicted, or unsupported, with quote grounding and a
  deterministic fallback. Live eLitigation pages supply the contextual
  evidence directly.
- [ ] **Scalability: evaluate thousands of queries daily.** The current path is
  synchronous and has not been load-tested or given production queueing,
  caching, rate limiting, and monitoring.

## Current architecture

The system has four boundaries:

1. **Browser capture** — `extension/src/content.js` ranks visible answer
   regions using semantic HTML, ARIA roles, layout/text structure, link
   density, exclusion hints, open shadow roots, and mutation stability. It
   emits `response_text`, canonical `response_markdown`, links, content
   blocks, offsets, candidate regions, and capture diagnostics. It is not tied
   to a LawNet-specific selector and does not intercept site network requests.
2. **Extension transport and UI** — `extension/src/background.js` waits for a
   stable capture, requests per-site access when necessary, and sends the
   payload to `127.0.0.1:8000`. `extension/src/popup.js` and
   `extension/src/popup-model.js` render the audit, including the unified
   verification-source section and separate source, name, link, existence, and
   rule-support signals.
3. **Deterministic backend pipeline** — `backend/app/extractors/` parses case
   names, neutral/parallel citations, context, links, and offsets. The API
   validates the capture, then `backend/app/pipeline.py` combines extraction,
   URL classification, source resolution, metadata comparison, and explicit
   uncertainty statuses.
4. **Verification authority** — with `ENABLE_LIVE_VERIFICATION=true` (the
   default), the backend checks a direct allowlisted source or performs a
   bounded exact search on official eLitigation, then verifies the discovered
   judgment metadata, and can extract contextual paragraphs from that same
   verified live page. The optional SQLite corpus is used only by offline mode
   and regression tests. A local corpus miss is never treated as proof that a
   judgment does not exist.

For the presentation-friendly overview, see
[`docs/architecture-overview.md`](docs/architecture-overview.md). For the
detailed component map, see [`docs/architecture.md`](docs/architecture.md).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Check the service with `curl http://127.0.0.1:8000/health`. Building the local
index is only required for offline mode or corpus maintenance:

```bash
python scripts/build_index.py
```

## Load the Chrome extension

1. Open `chrome://extensions` and enable **Developer mode**.
2. Choose **Load unpacked** and select this repository's `extension` directory
   (the directory containing `manifest.json`). Do not select
   `extension/test-pages`.
3. Serve the sample page in a separate terminal:

   ```bash
   python3 -m http.server 8080 --directory extension/test-pages
   ```

   Open `http://127.0.0.1:8080/sample-legal-ai-response.html` in Chrome.
4. Click the extension icon, grant the requested active-page access if Chrome
   asks, and choose **Audit response**.

The sample page includes verified, name-mismatched, fabricated, link-mismatched,
unsupported, and citation-free examples. Browser-internal pages cannot be
audited by Chrome extensions.

## API

```text
GET  /health
POST /api/v1/audit
POST /api/v1/sources/verify
```

The audit request accepts `response_text` and, when available,
`response_markdown`, plus links, content blocks, capture diagnostics, page URL,
and jurisdiction. The backend prefers canonical Markdown for extraction. A
minimal request is:

```bash
curl -s http://127.0.0.1:8000/api/v1/audit \
  -H 'content-type: application/json' \
  --data '{"response_text":"The court in Lim v Tan [2023] SGCA 12 held that a contract requires objective agreement.","links":[],"page_url":"http://localhost","jurisdiction":"Singapore"}'
```

The response identifies `verification_authority` as `elitigation` in the
default live mode or `local_corpus` in offline mode. `RULE_EVALUATOR=heuristic`
is the safe default for offline corpus mode. Set `RULE_EVALUATOR=llm_judge` to
enable the optional rubric-prompted contextual judge. It retrieves the best few
relevant paragraphs from the verified live eLitigation judgment, requires the
judge to quote the supplied evidence verbatim, and reports contextual evidence.
HTML judgments and text-based eLitigation PDFs are parsed in memory; PDF page
provenance is retained while only bounded excerpts are sent to the model. Missing
credentials, network failures, invalid responses, or failed grounding produce
an explicit unavailable result; live mode has no local-corpus fallback.
The full captured legal-AI response is also supplied to the judge, allowing it
to connect top-of-answer claims with LawNet-style references placed elsewhere
without assuming that citation layout for every answer.

The optional judge reads `OPENAI_API_KEY`, `LLM_MODEL` (or `OPENAI_MODEL`),
`OPENAI_BASE_URL`, and `LLM_TIMEOUT_SECONDS` from the repository-root `.env`
file. Keep `.env` out of source control; `.env.example` is the safe template.
To prepare a fine-tuning file
from labelled examples, run:

```bash
python scripts/agents/prepare_finetune.py
```

The checked-in `data/benchmarks/interpretation_gold.jsonl` contains 100
balanced synthetic-demo examples (20 per label), and
`data/benchmarks/interpretation_candidates.jsonl` contains the corresponding
unlabelled review candidates. Generate them again with:

```bash
python scripts/agents/adversarial_generator.py --count 20
python scripts/agents/prepare_finetune.py
```

These examples still require review and should not be treated as labels for
real judgments. The submission helper is dry-run by default; after review,
`python scripts/agents/submit_finetune.py --submit` uploads the JSONL and
creates a fine-tuning job. Fine-tuning is not started by the audit service.

### LoRA training path

When hosted OpenAI fine-tuning is unavailable, train a local/cloud adapter with
the optional stack in `requirements-finetune.txt`. The script creates a
deterministic, label-stratified 80/10/10 split and can prepare it without
loading a model:

```bash
python3.10 -m venv .venv-lora
source .venv-lora/bin/activate
pip install -r requirements-finetune.txt
python scripts/agents/train_lora.py --prepare-only
```

The default `Qwen/Qwen3-0.6B` is a small smoke-test model. For a real run on a
GPU, select a stronger open-weight base such as `openai/gpt-oss-20b`; use
`--use-4bit` only on a CUDA machine with bitsandbytes support:

```bash
python scripts/agents/train_lora.py \
  --base-model openai/gpt-oss-20b \
  --use-4bit \
  --gradient-checkpointing \
  --output-dir artifacts/lauudit-gpt-oss-lora
```

Review the held-out split and `training_metrics.json` before serving the
adapter. Serve the base model plus the saved adapter through an
OpenAI-compatible runtime, then set `OPENAI_BASE_URL` to that local/cloud
`/v1` endpoint and `LLM_MODEL` to the served adapter name. Keep the existing
grounding guardrail and heuristic fallback enabled.

Live verification is read-only and ephemeral. Direct URLs are fetched only
when their host is allowlisted; HTML judgments and text-based eLitigation PDFs
are supported without persisting source content. Citations without links use bounded exact
eLitigation search followed by direct judgment verification. Search pages,
malformed URLs, unknown hosts, failed metadata matches, and ambiguous captures
remain review-required findings. The explicit source-verification endpoint is
available for a retry.

## Optional offline corpus mode

The repository contains synthetic sample records under `data/corpus/`; they
are test fixtures, not legal authorities. For a permitted private corpus, add
metadata to `data/corpus/cases.jsonl` and documents to the configured document
directories, then run:

```bash
python scripts/build_index.py
```

The indexer validates required fields, duplicate identifiers/citations/names,
dates, URLs, document paths, and provenance. It builds a content-derived
SQLite snapshot atomically and never downloads `source_url`. Restricted source
files and generated indexes are Git-ignored. Do not commit real judgments
without confirming redistribution rights.

To re-check stale allowlisted source URLs without changing the audit path:

```bash
python scripts/verify_live_sources.py --delay 1
```

This maintenance command is bounded, read-only, and never saves fetched
judgment content.

## Tests

Run the complete local workflow:

```bash
.venv/bin/python scripts/test_all.py
```

For a faster loop without benchmarks:

```bash
.venv/bin/python scripts/test_all.py --skip-benchmarks
```

The declared frontend suite is run from `extension/`:

```bash
cd extension && npm test
```

The default backend tests are offline and do not contact legal-source sites:

```bash
.venv/bin/pytest backend/tests -m 'not live'
```

One opt-in end-to-end test exercises public eLitigation access. Run it only
after confirming that network access is permitted:

```bash
RUN_LIVE_TESTS=1 .venv/bin/pytest backend/tests -m live -q
```

This is an audit aid, not legal advice. Human review remains required for
metadata mismatches, ambiguous or low-confidence captures, unavailable
sources, and all contextual legal conclusions.
