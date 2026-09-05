# General page-reading validation

Lauudit's page reader is intentionally page-agnostic. It reads rendered DOM
content rather than screenshots, ranks candidate response regions, excludes
common page chrome, and preserves exact text/link offsets for backend matching.

## Capture stages

1. Traverse visible light DOM and open shadow roots.
2. Build leaf content blocks from headings, paragraphs, lists, quotations,
   preformatted text, tables, and equivalent block containers.
3. Generate candidate response regions from semantic roles, common structural
   elements, and text-bearing containers.
4. Score candidates using structure, semantic labels, link density, controls,
   exclusion hints, and document-body fallback penalties.
5. Capture the selected region with exact block and anchor offsets.
6. Report confidence, mutation stability, omitted regions, and inaccessible
   iframe limitations.

The reader does not claim to read content that is hidden, canvas-only,
cross-origin iframe content, closed shadow DOM, or virtualised content that has
not been rendered. Those cases produce diagnostics or should use explicit user
selection.

## Deterministic tests

The extension fixture suite covers semantic layouts, chat layouts, source-panel
exclusion, split text blocks, exact link offsets, open shadow roots, and DOM
stability after a mutation. Run it with:

```text
cd extension
npm run test:integration
```

The full repository validation remains:

```text
.venv/bin/python scripts/test_all.py
```

## Browser harness

`extension/tests/browser-harness.html` runs the real content script in a real
browser document with a minimal Chrome-runtime stub. It is useful for checking
browser-native `innerText`, layout visibility, MutationObserver behaviour, and
the resulting capture JSON without installing the extension.

Serve the extension directory locally and open
`/tests/browser-harness.html`, then select **Capture page**. The expected result
selects the assistant response, excludes navigation and source cards, reports a
stable semantic-DOM capture, and maps the eLitigation anchor exactly.

This harness is a browser smoke test, not a substitute for deterministic
fixtures. Live third-party pages should be used as additional smoke tests, not
as the only regression source, because their markup and content can change.
