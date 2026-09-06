/** @vitest-environment node */

import {readFileSync} from "node:fs";
import {fileURLToPath} from "node:url";
import {beforeEach, describe, expect, it, vi} from "vitest";

const backgroundPath = fileURLToPath(new URL("../src/background.js", import.meta.url));

function loadBackground(fetchMock) {
  const listeners = [];
  const chrome = {
    sidePanel: {setPanelBehavior: vi.fn(() => Promise.resolve())},
    tabs: {onRemoved: {addListener: vi.fn()}, sendMessage: vi.fn(), query: vi.fn()},
    scripting: {executeScript: vi.fn()},
    runtime: {
      onMessage: {addListener: (listener) => listeners.push(listener)},
      sendMessage: vi.fn(() => Promise.resolve()),
    },
  };
  const context = {
    chrome,
    console,
    fetch: fetchMock,
    setTimeout,
    clearTimeout,
  };
  const source = readFileSync(backgroundPath, "utf8");
  new Function("chrome", "fetch", "console", source)(chrome, fetchMock, console);
  return {chrome, listener: listeners[0]};
}

describe("background online-verification integration contract", () => {
  let fetchMock;

  beforeEach(() => {
    fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        status: "LIVE_VERIFIED",
        source_verified: true,
        final_url: "https://official.test/case-1",
        retrieved_at: "2026-09-06T00:00:00Z",
        metadata_match: {name: true, citation: true},
      }),
    }));
  });

  it("does not call the backend until an explicit verification message arrives", async () => {
    const {listener} = loadBackground(fetchMock);
    expect(fetchMock).not.toHaveBeenCalled();

    const response = await new Promise((resolve) => {
      listener({
        type: "VERIFY_SOURCE_ONLINE",
        payload: {
          source_url: "https://official.test/case-1",
          expected: {canonical_name: "Lim v Tan", neutral_citation: "[2023] SGCA 12"},
        },
      }, {}, resolve);
    });

    expect(response.ok).toBe(true);
    expect(response.result.status).toBe("LIVE_VERIFIED");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/sources/verify",
      expect.objectContaining({method: "POST"}),
    );
  });

  it("requests a stable page capture before sending an audit", async () => {
    const localAuditResult = {
      audit_id: "audit-browser",
      summary: {total_citations: 1},
      citations: [],
    };
    const liveAuditResult = {...localAuditResult, audit_id: "audit-browser-live"};
    fetchMock = vi.fn(async (url, options) => {
      if (url.endsWith("/audit")) {
        const body = JSON.parse(options.body);
        return {ok: true, json: async () => body.enable_live_verification ? liveAuditResult : localAuditResult};
      }
      return {ok: true, json: async () => ({})};
    });
    const {chrome, listener} = loadBackground(fetchMock);
    const payload = {
      response_text: "Lim v Tan [2023] SGCA 12",
      links: [],
      capture_diagnostics: {method: "semantic-dom", stable: true, confidence: 0.9},
    };
    chrome.tabs.query.mockResolvedValue([{id: 42}]);
    chrome.tabs.sendMessage.mockImplementation(async (_tabId, message) => {
      if (message.type === "COLLECT_RESPONSE_STABLE") return payload;
      return {};
    });

    const response = await new Promise((resolve) => {
      listener({type: "AUDIT_ACTIVE_TAB"}, {}, resolve);
    });

    expect(response).toEqual({ok: true, result: localAuditResult, live_pending: true});
    expect(chrome.tabs.sendMessage).toHaveBeenCalledWith(42, {type: "COLLECT_RESPONSE_STABLE"});
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/audit",
      expect.objectContaining({method: "POST"}),
    );
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toMatchObject({...payload, enable_live_verification: false});
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(fetchMock.mock.calls.filter(([url]) => url.endsWith("/audit"))).toHaveLength(2);
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toMatchObject({...payload, enable_live_verification: true});
    expect(chrome.tabs.sendMessage).toHaveBeenCalledWith(42, {type: "HIGHLIGHT_RESULTS", results: []});
  });

  it("explains when the active page cannot be accessed", async () => {
    const {chrome, listener} = loadBackground(fetchMock);
    chrome.tabs.query.mockResolvedValue([{id: 42}]);
    chrome.tabs.sendMessage.mockRejectedValue(new Error("Could not establish connection. Receiving end does not exist."));
    chrome.scripting.executeScript.mockRejectedValue(new Error(
      "Cannot access contents of the page. Extension manifest must request permission to access the respective host.",
    ));

    const response = await new Promise((resolve) => {
      listener({type: "AUDIT_ACTIVE_TAB"}, {}, resolve);
    });

    expect(response.ok).toBe(false);
    expect(response.error).toContain("Reload the extension and the tab");
    expect(response.error).toContain("chrome://");
  });
});
