# Architecture

Lauudit is a local Chrome Manifest V3 extension backed by a local FastAPI
service. The browser captures a visible legal-AI answer, sends a structured
payload to `127.0.0.1:8000`, and renders citation-level findings in the side
panel. The default audit path is live: official eLitigation resolution is the
authority for whether a cited Singapore judgment can be authenticated. The
local SQLite corpus is an internal deterministic first-pass mechanism, not the
formal verification authority and not a claim that the official corpus is
complete. The current scalability increment keeps live network latency bounded
and updates the browser asynchronously.

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
when needed, and forwards the payload to the local FastAPI service. It first
requests a local-corpus audit, then requests live verification asynchronously
and applies the later result through the existing highlight message channel.
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
4. returns authenticity, name, link, and explicit uncertainty statuses. Live
   mode does not currently determine whether a judgment supports the nearby
   legal proposition; contextual legal conclusions remain for human review.

Each live request uses a three-second timeout. Transport failures are tracked
by the thread-safe `backend/app/verifiers/circuit_breaker.py`, which opens
after three failures and cools down for 60 seconds. Successful verification
responses are cached by normalized URL plus expected metadata in the
process-local TTL cache from `backend/app/verifiers/live_cache.py`; the cache
holds up to 2,000 entries for one hour and stores only successful results.
When an audit contains multiple citations, the pipeline resolves them through a
bounded pool of at most eight workers while preserving citation order.

The live verifier is read-only and ephemeral. It does not persist judgments
into the repository or infer that a legal proposition is correct merely because
a judgment exists. The optional SQLite corpus supplies deterministic local
lookups and heuristic evidence for controlled regression tests. A local corpus
miss is reported as
`NOT_FOUND_IN_VERIFIED_CORPUS`; it is never proof that a judgment does not
exist. Formal audits use live verification as their authority.

## End-to-end data flow

1. The user selects **Audit response** or enables live selection in the side
   panel.
2. The content script waits for a stable rendered region and emits text,
   canonical Markdown, links, offsets, and capture diagnostics.
3. The service worker posts the payload to `/api/v1/audit`. The backend prefers
   `response_markdown`, extracts citations, and resolves live sources.
4. Live source resolution uses its timeout, breaker, cache, and bounded worker
   pool before returning the audit result.
5. The service worker sends the result and citation highlights to the side
   panel and content script. Asynchronous update handling prevents an older
   audit from overwriting a newer audit's highlights.
6. Direct API clients that omit `enable_live_verification` retain the
   deployment's configured default. The false override is reserved for
   controlled testing and maintenance; a deployment-level `false` cannot be
   overridden to enable network verification.

No page HTML, fetched judgment body, or source PDF is persisted by the live
audit path. The optional corpus index is built locally and atomically from
maintainer-provided permitted files.

## Scalability increment

The current target is thousands of audits per day at a modest peak rate. The
increment addresses the main bottleneck—waiting on public-source I/O—without
introducing a queue or a distributed service:

- `live_source.py` and `source_search.py` use three-second HTTP timeouts.
- `circuit_breaker.py` stops repeated transport failures for a 60-second
  cooldown after three failures.
- `live_cache.py` caches only confirmed-good results in a one-hour,
  2,000-entry process-local TTL cache.
- `pipeline.py` verifies citations concurrently with at most eight workers and
  keeps response ordering stable.
- `background.js` handles live-result updates asynchronously and prevents a
  slower audit from overwriting a newer UI state.

This is sufficient for the current MVP target. A multi-worker or multi-instance
deployment will need shared caching, rate limiting, load testing, and richer
operational monitoring; the current in-process cache and breaker are scoped to
one service process.

## Runtime configuration and testing

The primary runtime controls are:

- `ENABLE_LIVE_VERIFICATION=true` — default MVP mode; eLitigation is the
  verification authority for citation authenticity.
- `ENABLE_LIVE_VERIFICATION=false` — reserved for controlled testing,
  maintenance and controlled regression tests; formal
  deployments should keep live verification enabled.
- `AuditRequest.enable_live_verification=false` — controlled testing and
  maintenance override; it is not a formal audit mode.
- `RULE_EVALUATOR=heuristic` — enables conservative paragraph evidence checks
  during regression tests.
- `AUDIT_DB_PATH` and `CORPUS_CASES_PATH` — paths for test and maintenance
  corpus data.

The full local workflow is `python scripts/test_all.py`. It runs corpus
indexing, backend tests, deterministic gold/adversarial benchmarks, extension
syntax checks, frontend tests, and manifest validation. Live network tests are
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
- Contextual accuracy is not yet implemented: live verification authenticates the
  cited source but does not determine whether it supports the surrounding
  proposition. Local heuristic evidence is not a substitute for that
  contextual conclusion.
- Scalability is checked off for the current MVP target: bounded live I/O,
  circuit breaking, successful-result caching, per-citation parallelism, and
  asynchronous browser updates are implemented. Distributed
  production hardening remains future work.
