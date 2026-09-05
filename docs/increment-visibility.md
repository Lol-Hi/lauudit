# Increment visibility and verification guide

This document describes what a developer should expect to see after each Lauudit increment. A backend increment may change the JSON audit response without changing the Chrome popup until the frontend consumes the new fields.

## Current increment: URL provenance classifier

Branch: `branch-backend`

### Visible changes

- `GET /` returns Lauudit service information instead of a 404.
- The audit JSON now includes `source_status` and `source_url_normalized` for citations with hyperlinks.
- URL provenance is classified without making network requests.
- The existing popup layout is intentionally unchanged for now; it does not yet render these two new fields.

### Manual verification

```bash
cd /Users/luckheng/dev/lauudit
source .venv/bin/activate
python scripts/build_index.py
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
curl -s http://127.0.0.1:8000/
```

Send an audit request with an official eLitigation URL:

```bash
curl -s http://127.0.0.1:8000/api/v1/audit \
  -H 'content-type: application/json' \
  --data '{"response_text":"Lim v Tan [2023] SGCA 12 held that contractual agreement is assessed objectively.","links":[{"text":"Lim v Tan [2023] SGCA 12","href":"https://www.elitigation.sg/Documents/judgment.pdf","context":"Lim v Tan [2023] SGCA 12 held..."}]}'
```

The citation should contain:

```json
{
  "source_status": "OFFICIAL_ELITIGATION_SOURCE",
  "source_url_normalized": "https://www.elitigation.sg/Documents/judgment.pdf"
}
```

This does not mean that the URL is live or that it contains the cited case. It only means that the URL has official eLitigation-domain provenance. A search URL should produce `OFFICIAL_SOURCE_SEARCH_PAGE`; a normal unknown URL should produce `UNVERIFIED_EXTERNAL_URL`.

Singapore Law Watch Judgments links are classified as `TRUSTED_PUBLISHER_SOURCE`; its `/Judgments` and `/Results` pages are classified as `TRUSTED_PUBLISHER_SEARCH_PAGE`. These labels identify a publisher/discovery source only and do not replace local corpus confirmation.

## Increment 2: Frontend source-status display

### Visible changes

- The popup or side panel displays the source classification.
- Users can distinguish an official-domain URL from a locally ingested corpus source.
- Search-page links are visibly marked as search pages rather than direct case sources.
- Normalized source URLs can be copied or opened.

### Manual verification

Run the backend, serve the sample page, load the unpacked extension, and audit the page. Confirm that each citation card displays its source status and that the existing status, evidence, and disclaimer remain visible.

## Increment 3: Corpus provenance and ingestion improvements

### Visible changes

- `python scripts/build_index.py` prints clearer validation results.
- Audit results include a content-derived `corpus_snapshot`, `corpus_completeness`, and corpus notes.
- `python scripts/build_index.py` prints the metadata SHA-256 and states that no URLs were fetched.
- Successful builds write a Git-ignored `data/corpus/build_report.json` receipt.
- A case matched in the local corpus is labelled `KNOWN_CORPUS_SOURCE` when its hyperlink matches the indexed source URL.
- Rebuilding writes a temporary SQLite index and replaces the active index only after a successful build.
- Missing judgments remain `NOT_FOUND_IN_VERIFIED_CORPUS`; the interface must not say that the case does not exist.

### Manual verification

Add one permitted judgment and metadata record, rebuild the index, and audit a response citing it. Confirm that the response reports a `snapshot-*` ID and `partial` completeness, and inspect the build report. Try an invalid date, blank URL, duplicate name/alias, and missing document; confirm that each build reports an error without replacing the previous index. Confirm that no PDF or text file is downloaded by the API or extension.

## Increment 4: Source metadata confirmation

The backend now exposes an explicit online-verification operation. The normal
audit request remains deterministic and offline; the endpoint is disabled by
default and is not called by the extension yet.

### Visible changes

- An official URL may receive a separate metadata-confirmed status.
- The UI can show which fields were matched: case name, neutral citation, court, and decision date.
- Access-controlled or unavailable pages remain clearly distinguished from confirmed public judgments.
- `POST /api/v1/sources/verify` returns `LIVE_VERIFIED`, `LIVE_METADATA_MISMATCH`,
  `LIVE_SOURCE_UNAVAILABLE`, or a clear skipped/unsupported status.

### Manual verification

Enable the endpoint only for the run being tested:

```bash
ENABLE_LIVE_VERIFICATION=true uvicorn backend.app.main:app --host 127.0.0.1 --port 8001
```

Then POST one source URL and its expected metadata to
`http://127.0.0.1:8001/api/v1/sources/verify`. A matching public judgment
should return `LIVE_VERIFIED`, with `metadata_match` booleans and
`retrieved_at`; a redirect records `final_url`. Do not bypass authentication,
CAPTCHA, or access controls. Phase 3's frontend work is intentionally recorded
separately in `docs/phase-3-frontend-online-verification.md`.

## Increment 5: Safe verification test harness

### Visible changes

- The default test suite uses deterministic `httpx.MockTransport` responses and
  does not contact the internet.
- Redirects, external redirect targets, HTTP failures, metadata mismatches, and
  the Phase 3 payload contract are covered.
- Exactly one real-network eLitigation smoke test is registered as `live` and is
  skipped unless explicitly enabled.

### Manual verification

Run the default suite:

```bash
pytest -m "not live" -q
```

To opt into the sole live check, supply the exact case name visible on the
approved eLitigation page:

```bash
RUN_LIVE_TESTS=1 \
LIVE_CASE_NAME="Exact case name shown by eLitigation" \
LIVE_NEUTRAL_CITATION="[2026] SGCA 39" \
pytest -m live -q
```

The live test must return `LIVE_VERIFIED`; it should not be used to bypass
access controls, CAPTCHA, or rate limits.

## Increment 6: Rule-support retrieval improvements

### Visible changes

- Evidence cards now rank paragraphs using query coverage, term precision,
  phrase continuity, and operative holding language rather than raw term overlap.
- Confidence is calibrated separately for supported, uncertain, and unsupported
  retrieval outcomes.
- Fully supported deterministic retrieval can clear `needs_human_review` only
  for the retrieval signal; mismatches, weak evidence, and unresolved claims
  continue to require review.
- Claims with no supporting passage remain `UNSUPPORTED` or `UNCERTAIN`, rather than being presented as legal conclusions.

### Manual verification

Test one supported claim, one unsupported claim, and one ambiguous claim. Confirm that the paragraph text and paragraph numbers correspond to the local judgment, that the supported claim ranks the operative holding first, and that weak or absent evidence keeps `needs_human_review` true.

## Increment 6: PDF ingestion

### Visible changes

- The corpus can ingest permitted PDF judgments.
- Evidence includes page references in addition to paragraph references.
- OCR-derived text is marked separately when applicable.

### Manual verification

Index a permitted text-based PDF and an OCR PDF. Compare extracted paragraphs, page references, and error messages against the source documents.

## Regression checks for every increment

```bash
.venv/bin/pytest -q
.venv/bin/python scripts/build_index.py
.venv/bin/python scripts/run_benchmark.py data/benchmarks/gold_cases.jsonl
.venv/bin/python scripts/run_benchmark.py data/benchmarks/adversarial_cases.jsonl
```

For Chrome changes, also run:

```bash
node --check extension/src/background.js
node --check extension/src/content.js
node --check extension/src/popup.js
```
