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
});
