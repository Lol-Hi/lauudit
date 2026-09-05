/** @vitest-environment jsdom */

import {readFileSync} from "node:fs";
import {resolve} from "node:path";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";

const contentPath = resolve(process.cwd(), "src/content.js");
const fixturePath = (name) => resolve(process.cwd(), "tests/fixtures", name);

function loadContentScript() {
  const listeners = [];
  const chrome = {
    runtime: {
      onMessage: {addListener: (listener) => listeners.push(listener)},
      sendMessage: vi.fn(),
    },
  };
  new Function("chrome", readFileSync(contentPath, "utf8"))(chrome);
  return listeners[0];
}

function capture(listener) {
  let response;
  listener({type: "COLLECT_RESPONSE"}, {}, (payload) => { response = payload; });
  return response;
}

describe("general page-reading fixtures", () => {
  beforeEach(() => {
    globalThis.Node = window.Node;
    globalThis.NodeFilter = window.NodeFilter;
    vi.spyOn(window, "getComputedStyle").mockReturnValue({display: "block", visibility: "visible"});
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
      width: 100, height: 20, top: 0, right: 100, bottom: 20, left: 0,
    });
  });

  afterEach(() => vi.restoreAllMocks());

  for (const fixture of ["general-semantic.html", "general-chat.html"]) {
    it(`extracts the answer and citation mapping from ${fixture}`, () => {
      document.body.innerHTML = readFileSync(fixturePath(fixture), "utf8");
      const response = capture(loadContentScript());

      expect(response.response_text.length).toBeGreaterThan(80);
      expect(response.response_text).not.toContain("Unrelated source");
      expect(response.response_text).not.toContain("Source navigation");
      expect(response.links).toHaveLength(1);
      expect(response.links[0].mapping_status).toBe("EXACT");
      expect(response.response_text.slice(response.links[0].start, response.links[0].end)).toBe(response.links[0].text);
      expect(response.content_blocks.every((block) => response.response_text.slice(block.start, block.end) === block.text)).toBe(true);
      expect(response.capture_diagnostics.confidence).toBeGreaterThan(0.5);
    });
  }

  it("prefers a citation-bearing answer region over a longer text-only decoy", () => {
    document.body.innerHTML = `
      <div id="text-only-decoy">
        <p>This is a long interface explanation without any legal references.</p>
        <p>It should not be selected as the audit response when a citation-bearing region is available.</p>
        <p>It contains enough prose to be a competing candidate.</p>
      </div>
      <div id="actual-answer" aria-label="Answer content">
        <p>Lim v Tan [2023] SGCA 12 provides the relevant legal principle.</p>
      </div>
    `;
    const response = capture(loadContentScript());

    expect(response.capture_diagnostics.root).toContain("Answer content");
    expect(response.capture_diagnostics.warnings).not.toContain("MULTIPLE_CANDIDATE_REGIONS");
    expect(response.response_text).toContain("Lim v Tan [2023] SGCA 12");
  });
});
