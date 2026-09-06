import {afterAll, beforeAll, describe, expect, it, vi} from "vitest";

const auditResult = {
  audit_id: "audit-test",
  jurisdiction: "Singapore",
  corpus_snapshot: "snapshot-test",
  corpus_completeness: "partial",
  corpus_notes: "Test corpus",
  capture_diagnostics: {method: "semantic-dom", confidence: 0.94, stable: true, warnings: []},
  overall_status: "REVIEW_REQUIRED",
  summary: {total_citations: 1, verified_cases: 1, name_mismatches: 0, not_found: 0, link_errors: 0, unsupported_rules: 0},
  citations: [{
    occurrence_id: "occurrence-1",
    raw_text: "Lim v Tan [2023] SGCA 12",
    provided_name: "Lim v Tan",
    provided_citation: "[2023] SGCA 12",
    canonical_name: "Lim v Tan",
    source_url: "https://official.test/case-1",
    source_url_normalized: "https://official.test/case-1",
    source_status: "KNOWN_CORPUS_SOURCE",
    existence_status: "VERIFIED_EXISTS",
    name_status: "NAME_MATCH",
    link_status: "LINK_CONFIRMS_CASE",
    rule_support: "SUPPORTED",
    rule_confidence: 0.73,
    evidence: [],
    needs_human_review: false,
    status: "VERIFIED_EXISTS",
  }],
};

describe("popup and background message flow", () => {
  let sendMessage;
  let runtimeListener;

  beforeAll(async () => {
    document.body.innerHTML = `
      <button id="audit">Audit response</button>
      <button id="dynamic-selection-toggle">Enable live selection mode</button>
      <p id="dynamic-selection-state"></p>
      <p id="state"></p>
      <section id="summary"><div id="overall-status"></div><div id="audit-meta"></div><div id="metrics"></div></section>
      <section id="dynamic-selection-results"><p id="dynamic-selection-summary"></p><div id="dynamic-selection-list"></div></section>
      <section id="results"></section>`;
    sendMessage = vi.fn((message, callback) => {
      if (message.type === "AUDIT_ACTIVE_TAB") callback({ok: true, result: auditResult});
      if (message.type === "VERIFY_SOURCE_ONLINE") {
        callback({ok: true, result: {
          status: "LIVE_VERIFIED",
          source_verified: true,
          final_url: "https://official.test/case-1",
          retrieved_at: "2026-09-06T00:00:00Z",
          metadata_match: {name: true, citation: true},
        }});
      }
    });
    globalThis.chrome = {
      runtime: {
        sendMessage,
        lastError: null,
        onMessage: {addListener: vi.fn((listener) => { runtimeListener = listener; })},
      },
    };
    globalThis.navigator.clipboard = {writeText: vi.fn()};
    await import("../src/popup.js");
  });

  afterAll(() => {
    delete globalThis.chrome;
  });

  it("audits through the popup flow and renders the backend response", async () => {
    document.getElementById("audit").click();
    await Promise.resolve();

    expect(document.getElementById("state").textContent).toContain("Completed audit-test");
    expect(document.getElementById("results").textContent).toContain("Lim v Tan");
    expect(document.getElementById("summary").textContent).toContain("snapshot-test");
    expect(document.getElementById("summary").textContent).toContain("Confidence: 94%");
  });

  it("sends one deliberate online-verification request and renders its result", () => {
    document.querySelector(".verify-online").click();

    expect(sendMessage).toHaveBeenCalledWith(expect.objectContaining({
      type: "VERIFY_SOURCE_ONLINE",
      payload: {
        source_url: "https://official.test/case-1",
        expected: {canonical_name: "Lim v Tan", neutral_citation: "[2023] SGCA 12"},
      },
    }), expect.any(Function));
    expect(document.getElementById("results").textContent).toContain("Confirmed live judgment");
    expect(document.getElementById("results").textContent).toContain("name: match");
  });

  it("renders the asynchronous live upgrade after the local result", () => {
    runtimeListener({
      type: "AUDIT_LIVE_UPDATED",
      base_audit_id: "audit-test",
      result: {
        ...auditResult,
        audit_id: "audit-test-live",
        verification_authority: "elitigation",
        citations: [{...auditResult.citations[0], status: "LIVE_VERIFIED", source_status: "OFFICIAL_ELITIGATION_SOURCE"}],
      },
    });

    expect(document.getElementById("state").textContent).toContain("Live verification completed audit-test-live");
    expect(document.getElementById("summary").textContent).toContain("Verification authority: elitigation");
  });
});
