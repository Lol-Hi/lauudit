import {readFileSync} from "node:fs";
import {resolve} from "node:path";
import {describe, expect, it} from "vitest";

describe("extension page access contract", () => {
  it("grants host access for the same page scope as the content script", () => {
    const manifest = JSON.parse(readFileSync(resolve(process.cwd(), "manifest.json"), "utf8"));

    expect(manifest.content_scripts.some((script) => script.matches.includes("<all_urls>"))).toBe(true);
    expect(manifest.permissions).toContain("tabs");
    expect(manifest.host_permissions).not.toContain("<all_urls>");
    expect(manifest.optional_host_permissions).toEqual(expect.arrayContaining(["http://*/*", "https://*/*"]));
  });
});
