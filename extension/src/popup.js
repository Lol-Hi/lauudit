const state = document.getElementById("state");
const summary = document.getElementById("summary");
const results = document.getElementById("results");
const overallStatus = document.getElementById("overall-status");
const auditMeta = document.getElementById("audit-meta");
const metrics = document.getElementById("metrics");
const dynamicSelectionToggle = document.getElementById("dynamic-selection-toggle");
const dynamicSelectionState = document.getElementById("dynamic-selection-state");
const dynamicSelectionResults = document.getElementById("dynamic-selection-results");
const dynamicSelectionSummary = document.getElementById("dynamic-selection-summary");
const dynamicSelectionList = document.getElementById("dynamic-selection-list");
let dynamicSelectionEnabled = false;
let dynamicAudits = [];

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

const LINK_LABELS = {
  LINK_CONFIRMS_CASE: "Link confirms case",
  LINK_RESOLVES_TO_DIFFERENT_CASE: "Link points to another case",
  LINK_BROKEN_OR_INACCESSIBLE: "Link could not be confirmed",
  LINK_POINTS_TO_SEARCH_RESULTS: "Search page, not direct judgment",
  LINK_SPLIT_OR_AMBIGUOUS: "Split link needs review",
  NO_LINK_AVAILABLE: "No hyperlink supplied",
};

function displayLabel(value) {
  return String(value ?? "Unknown").replaceAll("_", " ");
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
  const value = item.source_url || "";
  const safeUrl = safeHttpUrl(value);
  if (!value) return "—";
  if (!safeUrl) return `<span class="unsafe-url">${esc(value)} (not a safe HTTP(S) link)</span>`;
  return `<a href="${esc(safeUrl)}" target="_blank" rel="noopener noreferrer">${esc(value)}</a>`;
}

function renderSummary(result) {
  const s = result.summary || {};
  overallStatus.className = `overall ${toneForStatus(result.overall_status)}`;
  overallStatus.innerHTML = `<span class="overall-label">Overall status</span><strong>${esc(result.overall_status || "UNKNOWN")}</strong>`;

  auditMeta.innerHTML = [
    `Audit: ${esc(result.audit_id || "—")}`,
    `Jurisdiction: ${esc(result.jurisdiction || "—")}`,
    `Corpus snapshot: ${esc(result.corpus_snapshot || "—")} ${result.corpus_snapshot ? '<button id="copy-snapshot" class="copy-button" type="button">Copy</button>' : ""}`,
    result.corpus_completeness ? `Coverage: ${esc(displayLabel(result.corpus_completeness))}` : "",
    result.corpus_notes ? `Corpus notes: ${esc(result.corpus_notes)}` : "",
    result.corpus_completeness ? "A corpus miss is not proof that a case does not exist." : "",
  ].filter(Boolean).map((value) => `<span>${value}</span>`).join("");

  const copyButton = document.getElementById("copy-snapshot");
  copyButton?.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(String(result.corpus_snapshot));
      copyButton.textContent = "Copied";
    } catch (_error) {
      copyButton.textContent = "Copy failed";
    }
  });

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
  if (!result || typeof result !== "object" || !Array.isArray(result.citations)) {
    summary.hidden = true;
    results.innerHTML = "<p>The backend returned an invalid audit response.</p>";
    state.textContent = "The backend returned an invalid audit response.";
    return;
  }
  summary.hidden = false;
  renderSummary(result);
  results.innerHTML = result.citations.length ? result.citations.map((item) => {
    const parallel = Array.isArray(item.parallel_citations) ? item.parallel_citations : [];
    const primary = item.provided_citation || parallel[0] || "—";
    const parallelOnly = parallel.filter((citation) => citation !== primary);
    const context = item.context_type === "footnote" && item.footnote_number
      ? `Footnote ${esc(item.footnote_number)}`
      : "Body text";
    const evidence = Array.isArray(item.evidence) ? item.evidence : [];
    const linkLabel = LINK_LABELS[item.link_status] || displayLabel(item.link_status);
    return `<article class="card ${citationTone(item)}">
      <h2>${esc(item.provided_name || item.raw_text || "Citation")}</h2>
      <p>${badge(item.status)}</p>
      <p>Primary citation: ${esc(primary)}</p>
      ${parallelOnly.length ? `<p>Parallel citations: ${parallelOnly.map((citation) => esc(citation)).join("; ")}</p>` : ""}
      <p>Context: ${context}</p>
      <p>Canonical: ${esc(item.canonical_name || "—")} ${item.case_id ? `(${esc(item.case_id)})` : ""}</p>
      <p>Source: ${badge(item.source_status, displayLabel(item.source_status))}<br>${sourceLink(item)}<br>Link: ${badge(item.link_status, linkLabel)}</p>
      <p>Existence: ${badge(item.existence_status)}<br>Name: ${badge(item.name_status)}<br>Rule: ${badge(item.rule_support)}${item.rule_confidence != null ? ` (${esc(item.rule_confidence)})` : ""}</p>
      ${item.explanation ? `<p>${esc(item.explanation)}</p>` : ""}
      ${item.needs_human_review ? '<p class="review-required">Human review required</p>' : ""}
      ${evidence.map((e) => `<blockquote>¶${esc(e.paragraph)}: ${esc(e.text)}</blockquote>`).join("")}
    </article>`;
  }).join("") : "<p>No supported Singapore case citation was detected on this page.</p>";
}

function renderDynamicSelectionResults() {
  const completed = dynamicAudits.filter((audit) => audit.result);
  const verified = completed.reduce((total, audit) => total + (Number(audit.result.summary?.verified_cases) || 0), 0);
  const needsReview = completed.filter((audit) => audit.result.overall_status !== "PASS").length;
  dynamicSelectionResults.hidden = !dynamicSelectionEnabled && !dynamicAudits.length;
  dynamicSelectionSummary.textContent = `${dynamicAudits.length} selected section(s) · ${completed.length} audited · ${verified} verified · ${needsReview} needs review`;
  dynamicSelectionList.innerHTML = dynamicAudits.length ? dynamicAudits.map((audit, index) => {
    if (audit.error) return `<article class="live-audit warn"><strong>Selection ${index + 1}</strong><p>${esc(audit.error)}</p></article>`;
    if (!audit.result) return `<article class="live-audit warn"><strong>Selection ${index + 1}</strong><p>Auditing…</p></article>`;
    return `<article class="live-audit ${toneForStatus(audit.result.overall_status)}"><strong>Selection ${index + 1}</strong> ${badge(audit.result.overall_status)}<span>${Number(audit.result.summary?.total_citations) || 0} citation(s)</span></article>`;
  }).join("") : "";
}

function updateDynamicAudit(selectionId, values) {
  const existing = dynamicAudits.find((audit) => audit.selectionId === selectionId);
  if (existing) Object.assign(existing, values);
  else dynamicAudits.push({selectionId, ...values});
  renderDynamicSelectionResults();
}

dynamicSelectionToggle.addEventListener("click", () => {
  const enabled = !dynamicSelectionEnabled;
  dynamicSelectionToggle.disabled = true;
  dynamicSelectionState.textContent = enabled ? "Enabling live selection mode…" : "Disabling live selection mode…";
  chrome.runtime.sendMessage({type: enabled ? "START_DYNAMIC_SELECTION" : "STOP_DYNAMIC_SELECTION"}, (message) => {
    dynamicSelectionToggle.disabled = false;
    if (chrome.runtime.lastError || !message || !message.ok) {
      dynamicSelectionState.textContent = "Unable to change selection mode. Check that Lauudit is running.";
      return;
    }
    dynamicSelectionEnabled = enabled;
    dynamicSelectionToggle.setAttribute("aria-pressed", String(enabled));
    dynamicSelectionToggle.textContent = enabled ? "Disable live selection mode" : "Enable live selection mode";
    dynamicSelectionState.textContent = enabled ? "Highlight a block of text; Lauudit will audit it automatically." : "Select a block of text to audit it automatically.";
    if (!enabled) dynamicAudits = [];
    renderDynamicSelectionResults();
  });
});

chrome.runtime.onMessage.addListener((message) => {
  if (message.type === "DYNAMIC_SELECTION_AUDIT_STARTED") {
    updateDynamicAudit(message.selection_id, {result: null, error: null});
  }
  if (message.type === "DYNAMIC_SELECTION_AUDIT_UPDATED") {
    updateDynamicAudit(message.selection_id, {result: message.result, error: null});
    state.textContent = "Live selection audit completed.";
    render(message.result);
  }
  if (message.type === "DYNAMIC_SELECTION_AUDIT_ERROR") {
    updateDynamicAudit(message.selection_id, {result: null, error: message.error});
  }
});

document.getElementById("audit").addEventListener("click", () => {
  state.textContent = "Auditing…";
  results.innerHTML = "";
  chrome.runtime.sendMessage({type: "AUDIT_ACTIVE_TAB"}, (message) => {
    if (chrome.runtime.lastError || !message || !message.ok) {
      state.textContent = "Backend unavailable. Start Lauudit locally and try again.";
      return;
    }
    state.textContent = `Completed ${message.result.audit_id}`;
    render(message.result);
  });
});
