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
- [ ] **Contextual accuracy: understand why a case matters.** The current MVP
  authenticates citation sources and reports explicit uncertainty, but does not
  yet determine whether a judgment supports the legal proposition around a
  citation. Human review remains required for contextual legal conclusions.
- [x] **Scalability: evaluate thousands of queries daily at the current MVP
  target load.** Live verification now has bounded timeouts, a circuit breaker,
  successful-result caching, bounded per-citation parallelism, and a
  asynchronous browser handling for live results. Production
  multi-instance queueing, shared caching, rate limiting, and load testing
  remain future hardening work.

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
   payload to `127.0.0.1:8000`. The browser receives a fast local-corpus result
   first, then receives a live-verification upgrade in the background. The
   popup and content script update both the citation cards and highlights when
   that upgrade arrives.
3. **Deterministic backend pipeline** — `backend/app/extractors/` parses case
   names, neutral/parallel citations, context, links, and offsets. The API
   validates the capture, then `backend/app/pipeline.py` combines extraction,
   URL classification, source resolution, metadata comparison, and explicit
   uncertainty statuses. Live citation resolutions run in bounded parallel
   workers while preserving response order.
4. **Verification authority** — with `ENABLE_LIVE_VERIFICATION=true` (the
   default), the backend checks a direct allowlisted source or performs a
   bounded exact search on official eLitigation, then verifies the discovered
   judgment metadata. The current live path is a source-authenticity check; it
   does not establish proposition-to-holding support. The optional SQLite
   corpus is used only for controlled maintenance and regression tests. A
   local corpus miss is never treated as proof that a judgment does not exist.

For the presentation-friendly overview, see
[`docs/architecture-overview.md`](docs/architecture-overview.md). For the
detailed component map, see [`docs/architecture.md`](docs/architecture.md).

## Scalability increment

The current scalability target is a few queries per minute at peak, or
thousands of audits per day. The implementation is designed to keep network
latency from blocking the whole workflow:

- Direct eLitigation and search requests use a three-second timeout.
- A thread-safe circuit breaker opens after three transport failures and cools
  down for 60 seconds.
- Successful live results are cached in-process for one hour, up to 2,000
  normalized URL/metadata keys. Failures and mismatches are not cached.
- Multiple citations in one audit are verified concurrently with at most eight
  workers, while their result order remains stable.
- The extension handles live-result updates asynchronously so verification does
  not require a second user action.

The cache is per process. A future multi-worker or multi-instance deployment
should move it to shared storage such as Redis and add operational rate
limiting and load testing.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Check the service with `curl http://127.0.0.1:8000/health`. Building the local
indexing is required for corpus maintenance and deterministic regression tests:

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

The formal audit result has `verification_authority` set to `elitigation`.
`local_corpus` is reserved for controlled maintenance and regression tests.
`RULE_EVALUATOR=heuristic` applies only to local corpus tests. Live
verification authenticates source metadata and returns explicit
`UNABLE_TO_EVALUATE` rule-support results rather than making a contextual legal
conclusion.

Formal deployments should keep `ENABLE_LIVE_VERIFICATION=true`; a false value
is reserved for controlled testing and maintenance.

Live verification is read-only and ephemeral. Direct URLs are fetched only
when their host is allowlisted. Citations without links use bounded exact
eLitigation search followed by direct judgment verification. Search pages,
malformed URLs, unknown hosts, failed metadata matches, and ambiguous captures
remain review-required findings. The explicit source-verification endpoint is
available for a retry.

## Local corpus maintenance

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

The default backend tests are deterministic and do not contact legal-source
sites:

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
