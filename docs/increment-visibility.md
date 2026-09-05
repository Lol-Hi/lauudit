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

## Next increment: citation extraction context

### Visible changes

- Parallel citations separated by commas, semicolons, or `and` are grouped into one audit citation.
- Case names can retain party suffixes such as `and another` and support more corporate-name tokens such as `(S) Pte Ltd`.
- Numbered footnote citations expose `context_type: "footnote"` and `footnote_number`.
- The audit JSON includes `parallel_citations`, `context_type`, and `footnote_number` on each citation.
- Hyperlink behavior is unchanged in this increment; split-link hardening is implemented in the backend-only Stage B increment below.

### Manual verification

Submit text containing a primary and reported parallel citation, then confirm one citation result contains both values in `parallel_citations`. Submit a numbered footnote citation and confirm its footnote metadata. No network request is made.

## Increment B: backend-only hyperlink hardening

### Visible changes

- Adjacent links whose combined text forms one citation are evaluated together.
- Split links using the same URL can produce `LINK_CONFIRMS_CASE`.
- Split links using different URLs produce `LINK_SPLIT_OR_AMBIGUOUS` and require review.
- Ambiguous links count toward `summary.link_errors` and cannot produce a false link confirmation.
- No Chrome extension file changes are required; the existing `text`, `href`, and `context` payload is sufficient for this first backend-only implementation.

### Manual verification

Send two adjacent `links` entries for one citation. Use the same `href` for both and confirm link confirmation. Use different `href` values and confirm `LINK_SPLIT_OR_AMBIGUOUS` with `status: "VERIFIED_EXISTS_LINK_MISMATCH"`. Exact single-anchor links and existing search-page behavior should remain unchanged.

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

This is deferred until eLitigation or another permitted source is available.

### Visible changes

- An official URL may receive a separate metadata-confirmed status.
- The UI can show which fields were matched: case name, neutral citation, court, and decision date.
- Access-controlled or unavailable pages remain clearly distinguished from confirmed public judgments.

### Manual verification

Use a permitted public judgment URL and compare the extracted metadata with the local citation. Do not bypass authentication, CAPTCHA, or access controls.

## Increment 5: Rule-support retrieval improvements

### Visible changes

- Evidence cards show better-ranked paragraphs.
- Confidence and human-review indicators become more informative.
- Claims with no supporting passage remain `UNSUPPORTED` or `UNCERTAIN`, rather than being presented as legal conclusions.

### Manual verification

Test one supported claim, one unsupported claim, and one ambiguous claim. Confirm that the paragraph text and paragraph numbers correspond to the local judgment.

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
