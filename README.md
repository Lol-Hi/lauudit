# Lauudit — Legal-AI citation auditor with live Singapore judgment verification

Lauudit is a local Chrome Manifest V3 extension and FastAPI service for
auditing citations in rendered legal-AI answers. The browser captures the
answer as structured text/Markdown with links and offsets, the backend extracts
and verifies citations, and the side panel shows citation-level findings. Live
verification is enabled by default: official eLitigation resolution is the
source of truth for citation authenticity in the MVP. No cloud database or
external LLM API is required at runtime.

## Problem statement progress

| Requirement | Current status |
| --- | --- |
| Hallucination: catch fake cases | **Checked off for the citation-authenticity MVP.** Deterministic extraction plus official eLitigation search/direct metadata matching detects fabricated, mismatched, and unresolvable citations. This does not prove that a legal proposition is correct. |
| Contextual accuracy: understand why a case matters | **In progress.** Live mode authenticates the source but deliberately reports `UNABLE_TO_EVALUATE` for proposition-to-holding support until that evidence path is implemented. |
| Scalability: evaluate thousands of queries daily | **Not yet checked off.** The current path is synchronous and has not been load-tested or given production queueing, caching, rate limiting, and monitoring. |

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
   default), the backend does not open or consult the local corpus. It checks a
   direct allowlisted source or performs a bounded exact search on official
   eLitigation, then verifies the discovered judgment metadata. With the flag
   set to `false`, the optional SQLite corpus provides offline existence,
   link, and conservative rule-support checks. A local corpus miss is never
   treated as proof that a judgment does not exist.

For the detailed component map, see
[`docs/architecture.md`](docs/architecture.md).

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
is used only by offline corpus mode; `local_model` is reserved for a future
inference adapter and currently returns `UNABLE_TO_EVALUATE` rather than
contacting a service.

Live verification is metadata-only and read-only. Direct URLs are fetched only
when their host is allowlisted. Citations without links use bounded exact
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
