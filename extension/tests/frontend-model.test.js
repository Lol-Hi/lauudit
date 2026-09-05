import {JSDOM} from "jsdom";
import {describe, expect, it} from "vitest";
import {
  canVerifyOnline,
  liveVerificationLabel,
  liveVerificationPayload,
  renderCitationCard,
  safeHttpUrl,
} from "../src/popup-model.js";

const citation = {
  occurrence_id: "occurrence-1",
  raw_text: "Lim v Tan [2023] SGCA 12; [2023] 2 SLR 100",
  provided_name: "Lim v Tan",
  provided_citation: "[2023] SGCA 12",
  parallel_citations: ["[2023] SGCA 12", "[2023] 2 SLR 100"],
  context_type: "footnote",
  footnote_number: "1",
  canonical_name: "Lim v Tan",
  case_id: "case-1",
  source_url: "https://official.test/case-1",
  source_url_normalized: "https://official.test/case-1",
  source_status: "KNOWN_CORPUS_SOURCE",
  existence_status: "VERIFIED_EXISTS",
  name_status: "NAME_MATCH",
  link_status: "LINK_SPLIT_OR_AMBIGUOUS",
  rule_support: "SUPPORTED",
  rule_confidence: 0.73,
  explanation: "Verified in the local corpus.",
  evidence: [{paragraph: 42, text: "The court held..."}],
  needs_human_review: true,
  status: "VERIFIED_EXISTS_LINK_MISMATCH",
};

describe("popup model", () => {
  it("renders grouped citations, context, provenance, evidence, and review state", () => {
    const dom = new JSDOM(`<main>${renderCitationCard(citation)}</main>`);
    const text = dom.window.document.body.textContent;

    expect(text).toContain("Primary citation: [2023] SGCA 12");
    expect(text).toContain("Parallel citations: [2023] 2 SLR 100");
    expect(text).toContain("Context: Footnote 1");
    expect(text).toContain("Known local corpus source");
    expect(text).toContain("Split link needs review");
    expect(text).toContain("Human review required");
    expect(text).toContain("¶42");
    expect(dom.window.document.querySelector("a")?.getAttribute("rel")).toBe("noopener noreferrer");
  });

  it("rejects unsafe source URLs without creating a link", () => {
    const unsafe = {...citation, source_url: "javascript:alert(1)", source_url_normalized: "javascript:alert(1)"};
    const dom = new JSDOM(`<main>${renderCitationCard(unsafe)}</main>`);

    expect(safeHttpUrl("javascript:alert(1)")).toBeNull();
    expect(dom.window.document.querySelector("a")).toBeNull();
    expect(dom.window.document.body.textContent).toContain("not a safe HTTP(S) link");
  });

  it("remains backward-compatible when optional provenance fields are absent", () => {
    const legacy = {raw_text: "Lim v Tan [2023] SGCA 12", evidence: []};
    const dom = new JSDOM(`<main>${renderCitationCard(legacy)}</main>`);

    expect(dom.window.document.body.textContent).toContain("Lim v Tan [2023] SGCA 12");
    expect(dom.window.document.body.textContent).toContain("Online verification unavailable");
  });

  it("constructs the documented online-verification payload only for direct URLs", () => {
    expect(canVerifyOnline(citation)).toBe(true);
    expect(liveVerificationPayload(citation)).toEqual({
      source_url: "https://official.test/case-1",
      expected: {
        canonical_name: "Lim v Tan",
        neutral_citation: "[2023] SGCA 12",
      },
    });
    expect(canVerifyOnline({...citation, source_status: "OFFICIAL_SOURCE_SEARCH_PAGE"})).toBe(false);
    expect(canVerifyOnline({...citation, link_status: "LINK_POINTS_TO_SEARCH_RESULTS"})).toBe(false);
  });

  it("labels live verification outcomes distinctly from offline status", () => {
    expect(liveVerificationLabel({status: "LIVE_VERIFIED"})).toContain("Confirmed live judgment");
    expect(liveVerificationLabel({status: "LIVE_METADATA_MISMATCH"})).toContain("metadata mismatch");
    expect(liveVerificationLabel({status: "LIVE_VERIFICATION_DISABLED"})).toContain("disabled");
  });
});
