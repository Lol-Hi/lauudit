const state = document.getElementById("state");
const summary = document.getElementById("summary");
const results = document.getElementById("results");

function esc(value) { const node = document.createElement("div"); node.textContent = value ?? ""; return node.innerHTML; }
function render(result) {
  const s = result.summary;
  summary.hidden = false;
  summary.innerHTML = `<div class="overall ${result.overall_status === "PASS" ? "good" : "bad"}">${esc(result.overall_status)}</div><div class="grid"><span>${s.total_citations} citations</span><span>${s.verified_cases} verified</span><span>${s.name_mismatches} name issues</span><span>${s.not_found} not found</span><span>${s.link_errors} link issues</span><span>${s.unsupported_rules} unsupported</span></div>`;
  results.innerHTML = result.citations.length ? result.citations.map((item) => `<article class="card ${item.status === "VERIFIED_EXISTS" ? "good" : "bad"}"><h2>${esc(item.raw_text)}</h2><p><strong>${esc(item.status)}</strong></p><p>Canonical: ${esc(item.canonical_name || "—")}</p><p>Source: ${item.source_url ? `<a href="${esc(item.source_url)}" target="_blank">${esc(item.source_url)}</a>` : "—"}</p><p>Link: ${esc(item.link_status)}<br>Rule: ${esc(item.rule_support)} (${item.rule_confidence})</p><p>${esc(item.explanation)}</p>${item.evidence.map((e) => `<blockquote>¶${e.paragraph}: ${esc(e.text)}</blockquote>`).join("")}</article>`).join("") : "<p>No supported Singapore case citation was detected on this page.</p>";
}

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
