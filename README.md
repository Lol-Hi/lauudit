# Lauudit — Local Singapore Legal-AI Citation Auditor

This repository is a first-iteration, local-only prototype. A Chrome Manifest V3 extension captures the visible rendered response and hyperlinks, sends them to a FastAPI backend on `127.0.0.1`, and receives a structured audit. No LangSmith, OpenRouter, cloud database, or external LLM API is required at runtime.

## What data is required?

To run the demo, no additional data is required: the repository contains two clearly marked synthetic sample judgments under `data/corpus/documents/`.

To audit real Singapore cases, the team must supply permitted plain-text judgments and metadata. The recommended discovery source is the Singapore Law Watch [Judgments page](https://www.singaporelawwatch.sg/Judgments); use its judgment/PDF link as provenance after the team has manually confirmed that the document may be retained and indexed. Put public/demo text in `data/corpus/documents/`, or put restricted text in the ignored `data/corpus/private_documents/` directory, and add one JSON object per line to `data/corpus/cases.jsonl`. The metadata must include `case_id`, `canonical_name`, `aliases`, `neutral_citation` or `reported_citations`, `court`, `court_code`, `decision_date`, `source_url`, `document_path`, and `source_type`. The corpus is not assumed to be comprehensive, so a missing case is reported as `NOT_FOUND_IN_VERIFIED_CORPUS`, never as proof that the case does not exist.

The sample records are synthetic and are useful only for wiring tests. They are not legal authorities.

## Setup

Navigate to your `lauudit` directory first

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
python scripts/build_index.py
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Check the backend with `curl http://127.0.0.1:8000/health`.

## Load the Chrome extension

1. Open `chrome://extensions`.
2. Enable **Developer mode**.
3. Choose **Load unpacked** and select `/Users/luckheng/dev/lauudit/extension` (the directory containing `manifest.json`). Do not select `extension/test-pages` or the sample HTML file; those are test-page content, not extension packages.
4. Open the sample page separately. The most reliable option is to serve it locally:

   ```bash
   python3 -m http.server 8080 --directory extension/test-pages
   ```

   Then open `http://127.0.0.1:8080/sample-legal-ai-response.html` in Chrome. Alternatively, open the HTML file directly with a `file:///...` URL and enable **Allow access to file URLs** on the extension’s Details page.

5. Click the extension icon and choose **Audit response**.

The extension reads the rendered DOM only. It does not intercept site network requests and sends captured data only to the local backend. The test page includes examples of verified, name-mismatched, fabricated, link-mismatched, unsupported, and citation-free cases.

## API

```text
GET  /health
POST /api/v1/audit
POST /api/v1/sources/verify
```

Example:

```bash
curl -s http://127.0.0.1:8000/api/v1/audit \
  -H 'content-type: application/json' \
  --data @- <<'JSON'
{"response_text":"The court in Lim v Tan [2023] SGCA 12 held that a contract requires objective agreement.","links":[],"page_url":"http://localhost","jurisdiction":"Singapore","as_of_date":"2026-09-05"}
JSON
```

`RULE_EVALUATOR=heuristic` is the default and is fully offline. `local_model` is reserved for a future Ollama/local inference adapter; the current implementation intentionally returns `UNABLE_TO_EVALUATE` for that mode instead of contacting a service.

Live source verification is a separate, explicit operation. It is disabled by
default and is enabled only for a deliberate maintenance or demonstration run
with `ENABLE_LIVE_VERIFICATION=true`. `POST /api/v1/sources/verify` validates
the source against the live-fetch allowlist, follows redirects, extracts page
metadata, and returns an ephemeral result. It does not run during
`POST /api/v1/audit`, write to the corpus, or save the fetched document.

## Corpus maintenance

After adding or changing `cases.jsonl` or documents, rebuild the index:

```bash
python scripts/build_index.py
```

The indexer validates required fields, document paths, duplicate case IDs, duplicate citations, duplicate canonical names/aliases, ISO decision dates, source URLs, and provenance timestamps. It exits non-zero when malformed records are found. Each successful build creates a content-derived corpus snapshot and records SHA-256 hashes for the metadata file and every indexed document. Rebuilding writes a temporary SQLite database and atomically replaces the active index only after validation and indexing succeed. A Git-ignored `data/corpus/build_report.json` receipt is also written for the successful build.

The build is intentionally offline: it never downloads `source_url`, PDF files, or text files. PDFs are an optional corpus-preparation artifact, not an extension-runtime artifact. If the team obtains permitted PDFs, keep them locally under `data/corpus/source_pdfs/`, extract approved text into `data/corpus/private_documents/` or `data/corpus/documents/`, and reference the text path from `cases.jsonl`. Both `source_pdfs/` and `private_documents/` are excluded from Git by default, as is the generated SQLite index. Do not commit real judgments unless the team has verified its redistribution rights.

Set `CORPUS_COMPLETENESS=partial` for the normal curated corpus. `comprehensive` should only be used after the team has documented the scope and coverage of the collection; it is not the default.

## Tests

Run the complete local verification workflow:

```bash
.venv/bin/python scripts/test_all.py
```

This rebuilds the corpus index, runs the backend tests, executes the gold and
adversarial benchmarks, checks extension JavaScript syntax, and validates the
extension manifest. Use `--skip-benchmarks` for a faster test-only loop.

The individual test command remains available when iterating on a specific
backend test:

```bash
pytest -m "not live" -q
```

The default suite never contacts the internet. There is exactly one opt-in
eLitigation smoke test; run it only after confirming access is permitted:

```bash
RUN_LIVE_TESTS=1 \
LIVE_CASE_NAME="Exact case name shown by eLitigation" \
LIVE_NEUTRAL_CITATION="[2026] SGCA 39" \
pytest -m live -q
```

The tests cover citation extraction, name normalization, exact/fuzzy/ambiguous existence, link outcomes, cautious rule support, and the API.

This is an audit aid, not legal advice. Its output requires human review, especially for `UNCERTAIN`, `AMBIGUOUS_MATCH`, corpus misses, link failures, and rule findings.
