const LINK_LABELS = {
  LINK_CONFIRMS_CASE: "Link confirms case",
  LINK_RESOLVES_TO_DIFFERENT_CASE: "Link points to another case",
  LINK_BROKEN_OR_INACCESSIBLE: "Link could not be confirmed",
  LINK_POINTS_TO_SEARCH_RESULTS: "Search page, not direct judgment",
  LINK_SPLIT_OR_AMBIGUOUS: "Split link needs review",
  NO_LINK_AVAILABLE: "No hyperlink supplied",
};

const SOURCE_LABELS = {
  KNOWN_CORPUS_SOURCE: "Known local corpus source",
  OFFICIAL_ELITIGATION_SOURCE: "Official eLitigation source",
  OFFICIAL_JUDICIARY_SOURCE: "Official Singapore Courts source",
  OFFICIAL_SOURCE_SEARCH_PAGE: "Official source search page",
  TRUSTED_PUBLISHER_SOURCE: "Trusted publisher source",
  TRUSTED_PUBLISHER_SEARCH_PAGE: "Trusted publisher search page",
  UNVERIFIED_EXTERNAL_URL: "Unverified external URL",
  MALFORMED_URL: "Malformed URL",
};

const LIVE_DISABLED_SOURCE_STATUSES = new Set([
  "OFFICIAL_SOURCE_SEARCH_PAGE",
  "TRUSTED_PUBLISHER_SEARCH_PAGE",
  "MALFORMED_URL",
]);

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function toneForStatus(status) {
  const value = String(status ?? "").trim().toUpperCase();
  if (["PASS", "VERIFIED_EXISTS", "LIVE_VERIFIED", "SUPPORTED", "LINK_CONFIRMS_CASE"].includes(value)) return "good";
  if (["REVIEW_REQUIRED", "NO_CITATIONS", "UNCERTAIN", "UNABLE_TO_EVALUATE", "AMBIGUOUS_MATCH", "SOURCE_UNAVAILABLE", "NO_LINK_AVAILABLE"].includes(value)) return "warn";
  if (value.includes("MISMATCH") || value.includes("NOT_FOUND") || value.includes("UNSUPPORTED") || value.includes("BROKEN") || value.includes("DIFFERENT_CASE") || value.includes("SEARCH_RESULTS")) return "bad";
  return "warn";
}

function citationTone(item) {
  if (item.live_verification?.status === "LIVE_VERIFIED") return "good";
  const tones = [item.status, item.existence_status, item.name_status, item.link_status, item.rule_support]
    .filter(Boolean)
    .map(toneForStatus);
  if (tones.includes("bad")) return "bad";
  if (!tones.length || tones.includes("warn")) return "warn";
  return "good";
}

function displayLabel(value) {
  return String(value ?? "Unknown").replaceAll("_", " ");
}

function sourceLabel(value) {
  return SOURCE_LABELS[value] || displayLabel(value);
}

function badge(value, label = displayLabel(value)) {
  return `<span class="status-badge ${toneForStatus(value)}">${esc(label)}</span>`;
}

function safeHttpUrl(value) {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch (_error) {
    return null;
  }
}

function sourceLink(item) {
  const displayValue = item.source_url || item.source_url_normalized || "";
  const safeUrl = safeHttpUrl(item.source_url_normalized || item.source_url);
  if (!displayValue) return "—";
  if (!safeUrl) return `<span class="unsafe-url">${esc(displayValue)} (not a safe HTTP(S) link)</span>`;
  const discovery = item.source_discovery === "OFFICIAL_ELITIGATION_SEARCH"
    ? " <span class=\"source-discovery\">(found by official search)</span>"
    : "";
  return `<a href="${esc(safeUrl)}" target="_blank" rel="noopener noreferrer">${esc(displayValue)}</a>${discovery}`;
}

function linkExplanation(status) {
  if (status === "LINK_SPLIT_OR_AMBIGUOUS") {
    return "The citation was split across links that point to different URLs. Lauudit did not choose one automatically.";
  }
  return "";
}

function canVerifyOnline(item) {
  return Boolean(
    item.source_url_normalized
    && safeHttpUrl(item.source_url_normalized)
    && !LIVE_DISABLED_SOURCE_STATUSES.has(item.source_status)
    && item.link_status !== "LINK_POINTS_TO_SEARCH_RESULTS"
    && (item.canonical_name || item.provided_name),
  );
}

function liveVerificationPayload(item) {
  const expected = {
    canonical_name: item.canonical_name || item.provided_name,
  };
  const optionalFields = {
    neutral_citation: item.provided_citation,
    court: item.court,
    court_code: item.court_code,
    decision_date: item.decision_date,
  };
  Object.entries(optionalFields).forEach(([key, value]) => {
    if (value) expected[key] = value;
  });
  return {source_url: item.source_url_normalized, expected};
}

function liveVerificationLabel(result) {
  if (result?.status === "LIVE_VERIFIED") return "Confirmed live judgment ✅";
  if (result?.status === "LIVE_METADATA_MISMATCH") return "Live page, metadata mismatch ⚠️";
  if (result?.status === "LIVE_VERIFICATION_DISABLED") return "Online verification disabled";
  return result?.reason || "Online verification unavailable";
}

function liveVerificationSummary(result) {
  if (!result) return "";
  const metadata = Object.entries(result.metadata_match || {})
    .map(([key, value]) => `${esc(key)}: ${value === true ? "match" : value === false ? "mismatch" : "unknown"}`)
    .join(" · ");
  const finalUrl = safeHttpUrl(result.final_url);
  const finalUrlMarkup = finalUrl
    ? `<a href="${esc(finalUrl)}" target="_blank" rel="noopener noreferrer">${esc(result.final_url)}</a>`
    : result.final_url ? esc(result.final_url) : "—";
  return `<p class="live-result-label">${esc(liveVerificationLabel(result))}</p>
    ${metadata ? `<p>Metadata: ${metadata}</p>` : ""}
    <p>Final URL: ${finalUrlMarkup}<br>Retrieved: ${esc(result.retrieved_at || "—")}</p>`;
}

function liveVerificationMarkup(item) {
  if (!canVerifyOnline(item)) {
    return '<p class="live-verification-disabled">Online verification unavailable for this source.</p>';
  }
  return `<div class="live-verification" data-occurrence-id="${esc(item.occurrence_id)}">
    <button class="verify-online secondary" type="button">${item.live_verification ? "Verify again" : "Verify online"}</button>
    <p class="live-disclosure">One read-only request to an allowlisted public source. This does not prove the legal proposition.</p>
    <div class="live-verification-result" aria-live="polite">${liveVerificationSummary(item.live_verification)}</div>
  </div>`;
}

function existenceMarkup(item) {
  if (item.live_verification?.status === "LIVE_VERIFIED") {
    return badge("LIVE_VERIFIED", "Verified by live source");
  }
  if (item.live_verification?.status === "LIVE_METADATA_MISMATCH") {
    return badge("LIVE_METADATA_MISMATCH", "Live source metadata mismatch");
  }
  return badge(item.existence_status);
}

function nameMarkup(item) {
  const match = item.live_verification?.metadata_match?.name;
  if (match === true) return badge("LIVE_VERIFIED", "Matched live source");
  if (match === false) return badge("LIVE_METADATA_MISMATCH", "Live source mismatch");
  return badge(item.name_status);
}

function renderCitationCard(item) {
  const parallel = Array.isArray(item.parallel_citations) ? item.parallel_citations : [];
  const primary = item.provided_citation || parallel[0] || "—";
  const parallelOnly = parallel.filter((citation) => citation !== primary);
  const context = item.context_type === "footnote" && item.footnote_number
    ? `Footnote ${esc(item.footnote_number)}`
    : "Body text";
  const evidence = Array.isArray(item.evidence) ? item.evidence : [];
  const linkLabel = LINK_LABELS[item.link_status] || displayLabel(item.link_status);
  const explanation = linkExplanation(item.link_status);
  return `<article class="card ${citationTone(item)}">
    <h2>${esc(item.provided_name || item.raw_text || "Citation")}</h2>
    <p>${badge(item.status)}</p>
    <p>Primary citation: ${esc(primary)}</p>
    ${parallelOnly.length ? `<p>Parallel citations: ${parallelOnly.map((citation) => esc(citation)).join("; ")}</p>` : ""}
    <p>Context: ${context}</p>
    <p>Canonical: ${esc(item.canonical_name || "—")} ${item.case_id ? `(${esc(item.case_id)})` : ""}</p>
    <p>Source: ${badge(item.source_status, sourceLabel(item.source_status))}<br>${sourceLink(item)}<br>Link: ${badge(item.link_status, linkLabel)}</p>
    ${explanation ? `<p class="link-explanation">${esc(explanation)}</p>` : ""}
    <p>Existence: ${existenceMarkup(item)}<br>Name: ${nameMarkup(item)}<br>Rule: ${badge(item.rule_support)}${item.rule_confidence != null ? ` (${esc(item.rule_confidence)})` : ""}</p>
    ${item.explanation ? `<p>${esc(item.explanation)}</p>` : ""}
    ${item.needs_human_review ? '<p class="review-required">Human review required</p>' : ""}
    ${liveVerificationMarkup(item)}
    ${evidence.map((e) => `<blockquote>¶${esc(e.paragraph)}: ${esc(e.text)}</blockquote>`).join("")}
  </article>`;
}

export {
  badge,
  canVerifyOnline,
  citationTone,
  displayLabel,
  esc,
  existenceMarkup,
  liveVerificationLabel,
  liveVerificationMarkup,
  liveVerificationPayload,
  liveVerificationSummary,
  nameMarkup,
  renderCitationCard,
  safeHttpUrl,
  sourceLabel,
  toneForStatus,
};
