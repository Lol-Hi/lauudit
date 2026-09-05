/** @vitest-environment jsdom */

import {readFileSync} from "node:fs";
import {resolve} from "node:path";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";

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

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("extracts the rendered response into exact blocks and link offsets", () => {
    const {listener} = loadContentScript();
    let response;

    listener({type: "COLLECT_RESPONSE"}, {}, (payload) => {
      response = payload;
    });

    expect(response.capture_diagnostics.root).toContain("main[answer-panel]");
    expect(response.capture_diagnostics.fallback_to_body).toBe(false);
    expect(response.capture_diagnostics.method).toBe("semantic-dom");
    expect(response.capture_diagnostics.confidence).toBeGreaterThan(0.6);
    expect(response.candidate_regions.some((candidate) => candidate.selected)).toBe(true);
    expect(response.excluded_regions.some((region) => region.region.startsWith("nav"))).toBe(true);
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

  it("selects a generic role-main response and excludes a complementary source region", () => {
    document.body.innerHTML = `
      <header>Global application header</header>
      <div id="app-shell">
        <section role="main" aria-label="Assistant response">
          <h2>General principle</h2>
          <p>A contract must be formed with sufficient certainty and intention.</p>
          <p>The court may consider the surrounding circumstances.</p>
        </section>
        <aside role="complementary" class="source-panel">
          <h2>Sources</h2><p>Unrelated source navigation and steps.</p>
        </aside>
      </div>
    `;
    const {listener} = loadContentScript();
    let response;

    listener({type: "COLLECT_RESPONSE"}, {}, (payload) => {
      response = payload;
    });

    expect(response.capture_diagnostics.root).toContain("section");
    expect(response.response_text).toContain("General principle");
    expect(response.response_text).not.toContain("Unrelated source navigation");
    expect(response.capture_diagnostics.warnings).not.toContain("BODY_FALLBACK_SELECTED");
  });

  it("waits for a quiet DOM before returning a stable capture", async () => {
    const {listener} = loadContentScript();
    document.querySelector("#answer-panel p").textContent = "The answer changed after streaming completed.";
    await new Promise((resolve) => setTimeout(resolve, 0));

    const response = await new Promise((resolve) => {
      listener({type: "COLLECT_RESPONSE_STABLE"}, {}, resolve);
    });

    expect(response.capture_diagnostics.stable).toBe(true);
    expect(response.capture_diagnostics.waited_ms).toBeGreaterThanOrEqual(300);
    expect(response.response_text).toContain("The answer changed after streaming completed.");
  });

  it("traverses open shadow DOM without treating the host as an opaque block", () => {
    document.body.innerHTML = `<div id="application-host"></div>`;
    const host = document.getElementById("application-host");
    const shadowRoot = host.attachShadow({mode: "open"});
    shadowRoot.innerHTML = `
      <main aria-label="Shadow response">
        <p>The response is rendered inside an open shadow root.</p>
        <p><a href="https://official.test/shadow-case">Lim v Tan [2023] SGCA 12</a></p>
      </main>`;
    const {listener} = loadContentScript();
    let response;

    listener({type: "COLLECT_RESPONSE"}, {}, (payload) => {
      response = payload;
    });

    expect(response.capture_diagnostics.root).toContain("main[Shadow response]");
    expect(response.response_text).toContain("open shadow root");
    expect(response.links[0].mapping_status).toBe("EXACT");
    expect(response.capture_diagnostics.open_shadow_root_count).toBe(1);
  });
});
