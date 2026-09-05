# Phase 3 — Extension online-verification handoff

The MVP implementation is now active on the integration branch. This document
records the frontend contract for automatic online verification and the
explicit retry action.

## Scope and invariants

- Keep the existing offline audit request and response rendering unchanged.
- Automatically verify eligible direct source URLs after each audit when
  `ENABLE_LIVE_VERIFICATION=true` (the MVP default), while retaining an
  explicit retry action on each citation card.
- When no hyperlink is supplied, search the official eLitigation judgments
  index by exact neutral citation, then verify the discovered direct URL.
- Do not download, cache, or persist the judgment in the extension. The
  backend endpoint returns metadata only and keeps the response ephemeral.
- Show live verification as a separate result from the offline `source_status`.
  An official domain is not the same claim as a confirmed live judgment.
- Do not add broad browser host permissions: the extension continues to talk to
  the local backend, which performs the allowlisted server-side fetch.

## Planned `extension/src/background.js` changes

The extension retains a distinct message type and endpoint constant for manual
retries. The existing `AUDIT_ACTIVE_TAB` message remains unchanged; automatic
verification is performed by the backend as part of the audit response.

```js
const LIVE_VERIFY_URL = `${BACKEND_URL}/api/v1/sources/verify`;

// In the existing message switch:
case "VERIFY_SOURCE_ONLINE": {
  const response = await fetch(LIVE_VERIFY_URL, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(message.payload),
  });
  return { ok: response.ok, result: await response.json() };
}
```

The payload should contain only the selected citation's `source_url` and
metadata already present in the audit result:

```js
{
  source_url: citation.source_url_normalized,
  expected: {
    canonical_name: citation.canonical_name || citation.provided_name,
    neutral_citation: citation.provided_citation,
    court_code: citation.court_code,
    decision_date: citation.decision_date,
  },
}
```

Before sending, omit empty optional fields and disable the action when
`source_url_normalized` is absent or the source is a search-page status.

## Planned popup changes

1. Retain the latest `AuditResponse` in memory as `lastAuditResult`.
2. Render an automatic live-verification result when the citation includes
   `live_verification`.
3. Add a `Verify online` or `Verify again` button to each citation card only when the citation
   has a direct normalized source URL.
4. On click, send `VERIFY_SOURCE_ONLINE` for that card and render a pending,
   success, mismatch, unavailable, or disabled state in the same card.
5. Display the returned `final_url`, `retrieved_at`, and field-level
   `metadata_match` values. Do not overwrite the offline `source_status`.
6. Include a concise disclosure: “This performs one read-only request to an
   allowlisted public source. It does not prove the legal proposition and may
   be unavailable.”

Illustrative rendering logic:

```js
function liveVerificationLabel(result) {
  if (result.status === "LIVE_VERIFIED") return "Confirmed live judgment ✅";
  if (result.status === "LIVE_METADATA_MISMATCH") return "Live page, metadata mismatch ⚠️";
  if (result.status === "LIVE_VERIFICATION_DISABLED") return "Online verification disabled";
  return result.reason || "Online verification unavailable";
}
```

## Acceptance checks before implementation

- The audit endpoint automatically checks an eligible official direct URL when
  live verification is enabled, and remains offline when the setting is false.
- A citation without a hyperlink can be found through the official search index
  and then confirmed against the discovered judgment metadata.
- No extension code writes source HTML, PDF bytes, or fetched metadata to
  `chrome.storage`.
- A direct judgment URL can be verified with one deliberate click.
- Search pages, external redirects, HTTP errors, and metadata mismatches are
  visibly distinct from `LIVE_VERIFIED`.
- `node --check` passes for every changed extension script, and the existing
  popup audit flow still works when the live endpoint is disabled.
