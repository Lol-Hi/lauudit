# Architecture

Lauudit is a local Chrome Manifest V3 extension backed by a local FastAPI
service. The browser captures a visible legal-AI answer, sends a structured
payload to `127.0.0.1:8000`, and renders citation-level findings in the side
panel. The default audit path is live: official eLitigation resolution is the
authority for whether a cited Singapore judgment can be authenticated. The
local SQLite corpus is an optional offline mode, not a claim that the official
corpus is complete.

## Browser capture

`extension/src/content.js` builds a page-agnostic capture from the rendered
page. It ranks candidate answer regions using semantic HTML, ARIA roles, text
structure, layout visibility, link density, exclusion hints, and mutation
stability. It traverses open shadow roots, preserves block and hyperlink
offsets, and reconstructs canonical Markdown where the page exposes structured
text. It reports `response_text`, `response_markdown`, links, content blocks,
candidate regions, excluded regions, and capture diagnostics. No LawNet-only
selector is required and the extension does not intercept site network
requests.

`extension/src/background.js` waits for a quiet capture, requests host access
when needed, and forwards the payload to the local FastAPI service.
`extension/src/popup.js` and `extension/src/popup-model.js` render the audit
summary, citation statuses, live verification results, and a unified
verification-source section. The renderer keeps source discovery, source
authenticity, name matching, link mapping, and rule support as separate signals
so one cannot silently stand in for another.

The side panel is declared by `extension/manifest.json` and loads the shared
popup renderer from `extension/src/sidepanel.html`; there is no second,
diverging side-panel implementation. The extension requests the active page's
host access only when required and restricts its backend permissions to the
local HTTP service.

## Backend pipeline

`backend/app/api/routes.py` validates the request and exposes the audit and
explicit source-verification endpoints. `backend/app/extractors/citations.py`
deterministically extracts neutral citations, case names, parallel citations,
context, and source offsets from the captured Markdown/text. Link mapping and
URL classification are handled separately.

With `ENABLE_LIVE_VERIFICATION=true` (the default),
`backend/app/pipeline.py`:

1. extracts citations from canonical Markdown when available;
2. resolves a direct allowlisted source or performs a bounded exact search on
   the official eLitigation index;
3. fetches only approved public judgment content, follows only approved
   redirects, and compares the discovered name/citation metadata with the
   citation; and
4. returns authenticity, name, link, and rule-support results. When
   `RULE_EVALUATOR=llm_judge`, it extracts contextual paragraphs from the
   verified live judgment in memory.

The live verifier is read-only and ephemeral. It does not persist judgments
into the repository or infer that a legal proposition is correct merely because
a judgment exists. A successful source match therefore checks citation
authenticity/existence. With `llm_judge`, proposition-to-holding support is
evaluated against the best few relevant paragraphs extracted from that verified
live judgment. HTML and text-based eLitigation PDFs are supported; PDF pages
are parsed in memory and the judge receives bounded excerpts with page
provenance rather than an unbounded whole-document prompt.

With `ENABLE_LIVE_VERIFICATION=false`, the backend opens the optional SQLite
corpus and uses its exact/fuzzy lookup, link comparison, and paragraph-level
rule-support heuristics. A local corpus miss is reported as
`NOT_FOUND_IN_VERIFIED_CORPUS`; it is never proof that a judgment does not
exist.

## End-to-end data flow

1. The user selects **Audit response** or enables live selection in the side
   panel.
2. The content script waits for a stable rendered region and emits text,
   canonical Markdown, links, offsets, and capture diagnostics.
3. The service worker posts that payload to `/api/v1/audit` on the local
   backend. The backend prefers `response_markdown` and falls back to
   `response_text` for older clients.
4. Citation extraction creates one audit record per citation occurrence,
   retaining parallel citations and body/footnote context.
5. Live mode resolves or searches eLitigation, verifies source metadata, and
   optionally extracts live judgment paragraphs or PDF text for the contextual
   judge. The judge also receives the complete captured legal-AI response, so
   citations at the bottom of a LawNet-style answer can be evaluated against
   claims presented elsewhere in the answer without hard-coding that layout.
   Offline mode continues to query SQLite for deterministic regression tests.
6. The side panel displays the result while preserving separate source,
   existence, name, link, rule, and human-review statuses.

No page HTML, fetched judgment body, or source PDF is persisted by the live
audit path. The optional corpus index is built locally and atomically from
maintainer-provided permitted files.

## Runtime configuration and testing

The primary runtime controls are:

- `ENABLE_LIVE_VERIFICATION=true` — default MVP mode; eLitigation is the
  verification authority and the live judgment supplies contextual evidence.
- `ENABLE_LIVE_VERIFICATION=false` — deterministic offline corpus mode for
  local development and regression benchmarks.
- `RULE_EVALUATOR=heuristic` — enables conservative paragraph evidence checks
  in offline mode.
- `RULE_EVALUATOR=llm_judge` — retrieves the best few relevant paragraphs and
  sends bounded evidence to an optional rubric-prompted model. The result is
  accepted only when the model quotes a source span verbatim; absent
  credentials, model failures, malformed output, and failed grounding return
  an explicit unavailable result; live mode has no local-corpus fallback.
- `AUDIT_DB_PATH` and `CORPUS_CASES_PATH` — optional paths for offline corpus
  data.

For a fine-tuned replacement model, set `LLM_MODEL` to the fine-tuned model
identifier after the training job completes. The synthetic-demo dataset is
generated by `scripts/agents/adversarial_generator.py` and converted by
`scripts/agents/prepare_finetune.py`. The explicit operator helper
`scripts/agents/submit_finetune.py` is dry-run by default and creates the job
only when invoked with `--submit`; training is never part of an audit request.

The provider-independent LoRA path is `scripts/agents/train_lora.py`. It uses
optional Transformers, PEFT, and TRL dependencies, writes deterministic
label-stratified train/validation/test splits, and supports NF4 QLoRA on CUDA.
The default small model is for smoke tests; stronger open-weight bases require
a suitable GPU. The trained adapter must be served behind an
OpenAI-compatible `/v1/chat/completions` endpoint before `llm_client.py` can
use it.

The full local workflow is `python scripts/test_all.py`. It runs corpus
indexing, backend tests, offline gold/adversarial benchmarks, extension syntax
checks, frontend tests, and manifest validation. Live network tests are
separate and opt-in. This split keeps source-authenticity behavior explicit
while making the regression suite deterministic.

## Trust and uncertainty boundaries

Live fetching is limited to the configured official eLitigation, judiciary, and
trusted publisher hosts. Search pages, malformed URLs, arbitrary external
links, failed metadata matches, ambiguous extraction, and low-confidence page
captures remain visible as review-required findings. The system stores neither
the browser page nor fetched judgment content as part of an audit request.

The three problem areas are intentionally separate:

- Hallucination/citation authenticity is the checked-off MVP slice: the system
  can detect fabricated or mismatched citations by deterministic extraction
  plus live official-source metadata verification.
- Contextual accuracy has an opt-in evidence path in both offline and live
  modes: live audits compare a surrounding proposition with a paragraph
  extracted from the verified eLitigation judgment.
- Scalability is not yet checked off: the current request path is synchronous
  and has not been load-tested or equipped with production queueing, caching,
  rate limiting, and operational monitoring for thousands of daily queries.
