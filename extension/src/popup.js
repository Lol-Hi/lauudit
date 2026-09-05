const state = document.getElementById("state");
const summary = document.getElementById("summary");
const results = document.getElementById("results");
const overallStatus = document.getElementById("overall-status");
const auditMeta = document.getElementById("audit-meta");
const metrics = document.getElementById("metrics");

function esc(value) { const node = document.createElement("div"); node.textContent = value ?? ""; return node.innerHTML; }

function toneForStatus(status) {
  const value = String(status ?? "").trim().toUpperCase();
  if (["PASS", "VERIFIED_EXISTS", "SUPPORTED", "LINK_CONFIRMS_CASE"].includes(value)) return "good";
  if (["REVIEW_REQUIRED", "NO_CITATIONS", "UNCERTAIN", "UNABLE_TO_EVALUATE", "AMBIGUOUS_MATCH", "SOURCE_UNAVAILABLE", "NO_LINK_AVAILABLE"].includes(value)) return "warn";
  if (value.includes("MISMATCH") || value.includes("NOT_FOUND") || value.includes("UNSUPPORTED") || value.includes("BROKEN") || value.includes("DIFFERENT_CASE") || value.includes("SEARCH_RESULTS")) return "bad";
  return "warn";
}

function citationTone(item) {
  const tones = [item.status, item.existence_status, item.name_status, item.link_status, item.rule_support]
    .filter(Boolean)
    .map(toneForStatus);
  if (tones.includes("bad")) return "bad";
  if (!tones.length || tones.includes("warn")) return "warn";
  return "good";
}

function badge(value) {
  return `<span class="status-badge ${toneForStatus(value)}">${esc(value || "Unknown")}</span>`;
}

function renderSummary(result) {
  const s = result.summary || {};
  overallStatus.className = `overall ${toneForStatus(result.overall_status)}`;
  overallStatus.innerHTML = `<span class="overall-label">Overall status</span><strong>${esc(result.overall_status || "UNKNOWN")}</strong>`;

  auditMeta.innerHTML = [
    `Audit: ${esc(result.audit_id || "—")}`,
    `Jurisdiction: ${esc(result.jurisdiction || "—")}`,
    `Corpus: ${esc(result.corpus_snapshot || "—")}`,
  ].map((value) => `<span>${value}</span>`).join("");

  const values = [
    ["Citations", s.total_citations],
    ["Verified", s.verified_cases],
    ["Name issues", s.name_mismatches],
    ["Not found", s.not_found],
    ["Link issues", s.link_errors],
    ["Unsupported rules", s.unsupported_rules],
  ];
  metrics.innerHTML = values.map(([label, value]) => `
    <div class="metric">
      <span class="metric-value">${Number(value) || 0}</span>
      <span class="metric-label">${label}</span>
    </div>
  `).join("");
}

function render(result) {
  summary.hidden = false;
  renderSummary(result);
  results.innerHTML = result.citations.length ? result.citations.map((item) => `<article class="card ${citationTone(item)}"><h2>${esc(item.raw_text)}</h2><p>${badge(item.status)}</p><p>Canonical: ${esc(item.canonical_name || "—")}</p><p>Source: ${item.source_url ? `<a href="${esc(item.source_url)}" target="_blank">${esc(item.source_url)}</a>` : "—"}</p><p>Link: ${badge(item.link_status)}<br>Rule: ${badge(item.rule_support)} (${item.rule_confidence})</p><p>${esc(item.explanation)}</p>${item.evidence.map((e) => `<blockquote>¶${e.paragraph}: ${esc(e.text)}</blockquote>`).join("")}</article>`).join("") : "<p>No supported Singapore case citation was detected on this page.</p>";
}

document.getElementById("audit-selection").addEventListener("click", () => {
  state.textContent = "Auditing selected text…";
  results.innerHTML = "";
  chrome.runtime.sendMessage({type: "AUDIT_SELECTED_TEXT"}, (message) => {
    if (chrome.runtime.lastError || !message || !message.ok) {
      state.textContent = chrome.runtime.lastError?.message || message?.error || "Selected-text audit failed.";
      return;
    }
    state.textContent = `Completed ${message.result.audit_id}`;
    render(message.result);
  });
});

document.getElementById("audit").addEventListener("click", () => {
  state.textContent = "Auditing…";
  results.innerHTML = "";
  chrome.runtime.sendMessage({type: "AUDIT_ACTIVE_TAB"}, (message) => {
    if (chrome.runtime.lastError || !message || !message.ok) {
      state.textContent = chrome.runtime.lastError?.message || message?.error || "Audit failed.";
      return;
    }
    state.textContent = `Completed ${message.result.audit_id}`;
    render(message.result);
  });
});
