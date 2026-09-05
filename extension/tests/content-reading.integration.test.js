/** @vitest-environment jsdom */

import {readFileSync} from "node:fs";
import {resolve} from "node:path";
import {beforeEach, describe, expect, it, vi} from "vitest";

const contentPath = resolve(process.cwd(), "src/content.js");

function loadContentScript() {
  const listeners = [];
  const chrome = {
    runtime: {
      onMessage: {addListener: (listener) => listeners.push(listener)},
      sendMessage: vi.fn(),
    },
  };
  const source = readFileSync(contentPath, "utf8");
  new Function("chrome", source)(chrome);
  return {chrome, listener: listeners[0]};
}

describe("content script page reading", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <nav>Navigation that must not enter the audit payload</nav>
      <main id="answer-panel">
        <h1>When is a contract enforceable?</h1>
        <p>A contract is enforceable when its formation requirements are satisfied.</p>
        <ul>
          <li>
            <a href="https://www.elitigation.sg/gdviewer/s/1995_SGHC_114">
              Shell Eastern Petroleum (Pte) Ltd v Chuan Hong Auto (Pte) Ltd [1995] SGHC 114
            </a>
          </li>
        </ul>
        <aside>Sources and steps that must not enter the response payload</aside>
      </main>
    `;
    globalThis.NodeFilter = window.NodeFilter;
    globalThis.Node = window.Node;
    vi.spyOn(window, "getComputedStyle").mockReturnValue({display: "block", visibility: "visible"});
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
      width: 100,
      height: 20,
      top: 0,
      right: 100,
      bottom: 20,
      left: 0,
    });
  });

  it("extracts the rendered response into exact blocks and link offsets", () => {
    const {listener} = loadContentScript();
    let response;

    listener({type: "COLLECT_RESPONSE"}, {}, (payload) => {
      response = payload;
    });

    expect(response.capture_diagnostics.root).toContain("main[answer-panel]");
    expect(response.capture_diagnostics.fallback_to_body).toBe(false);
    expect(response.response_text).toContain("When is a contract enforceable?");
    expect(response.response_text).toContain("Shell Eastern Petroleum (Pte) Ltd v Chuan Hong Auto (Pte) Ltd [1995] SGHC 114");
    expect(response.response_text).not.toContain("Navigation that must not enter");
    expect(response.response_text).not.toContain("Sources and steps that must not enter");

    expect(response.content_blocks.length).toBeGreaterThanOrEqual(3);
    response.content_blocks.forEach((block) => {
      expect(response.response_text.slice(block.start, block.end)).toBe(block.text);
    });

    expect(response.links).toHaveLength(1);
    const [link] = response.links;
    expect(link.block_id).toBe(response.content_blocks.at(-1).id);
    expect(response.response_text.slice(link.start, link.end)).toBe(link.text);
    expect(link.href).toBe("https://www.elitigation.sg/gdviewer/s/1995_SGHC_114");
  });
});
