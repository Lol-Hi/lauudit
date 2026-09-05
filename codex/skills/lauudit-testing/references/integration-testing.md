# Browser/API integration testing

Use this guide for tests that cross a process or UI boundary: FastAPI over HTTP,
the extension background service worker, a real browser tab, or the popup/side panel.

## API integration

Use FastAPI `TestClient` for in-process endpoint tests. Use a live Uvicorn server only
when the test specifically verifies HTTP transport, extension messaging, or browser
behavior. Bind test services to loopback and use isolated test data/configuration.

Verify that:

- the offline `/api/v1/audit` path does not invoke live verification;
- `/api/v1/sources/verify` is explicit, allowlisted, metadata-only, and ephemeral;
- disabled, untrusted-host, redirect, unavailable, and metadata-mismatch states are
  preserved through the API response;
- external source HTML/PDF bytes are never written to extension storage or test
  artifacts.

Use mocked or fixture-backed source responses for deterministic tests. Do not make
uncontrolled requests to public legal sites in the normal integration suite.

## Extension/browser integration

If a configured Playwright, Chrome extension harness, or equivalent suite exists, use
its declared command. The harness should load the unpacked `extension/` directory,
serve or open `extension/test-pages/sample-legal-ai-response.html`, and exercise:

1. opening the side panel and auditing the visible response;
2. citation cards, highlights, parallel citations, and footnote context;
3. safe source-link behavior and backend-unavailable messaging;
4. deliberate `Verify online` clicks only for direct normalized source URLs;
5. live verification success, mismatch, disabled, and unavailable results;
6. confirmation that no source document is downloaded or persisted by the extension.

Do not install an extension, grant new browser permissions, or log into external sites
as part of an automated test run without the required user authorization. If the
browser harness or display is unavailable, report the integration suite as skipped
with the concrete environment reason rather than converting it into a unit test.

## Reporting

Separate API integration, browser integration, and manual checks. Include the server
command/configuration, browser harness command, fixture or mock source used, and any
skipped checks. A passing backend `pytest` suite alone does not establish extension
integration coverage.
