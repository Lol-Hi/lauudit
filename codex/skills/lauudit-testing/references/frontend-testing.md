# Frontend testing

Use this guide for tests that execute extension JavaScript or render popup/side-panel UI
without requiring a real browser tab.

## Discover the suite

Inspect the repository before choosing a command:

```bash
rg --files -g 'package.json' -g '*test*' -g '*spec*' -g 'vitest.config.*' -g 'jest.config.*'
```

Prefer the scripts declared by the nearest `package.json`. Typical commands may be
`npm test`, `npm run test:frontend`, or `npx vitest run`, but do not run or invent them
when the repository does not declare the corresponding tool.

The centralized `scripts/test_all.py` workflow runs the declared frontend suite when
`extension/package.json` is present, in addition to extension syntax and manifest checks.
Those static checks do not replace renderer or message-behavior tests.

## Expected coverage

Frontend unit tests should exercise the renderer and pure helpers with mocked `chrome`
APIs and a lightweight DOM. At minimum cover:

- corpus snapshot, completeness, notes, and the corpus-miss reminder;
- grouped parallel citations and body/footnote context;
- source-status and link-status labels, including split-link explanations;
- missing optional backend fields for backward compatibility;
- safe HTTP(S) URL handling and `noopener noreferrer` links;
- invalid backend responses and backend-unavailable states;
- live-verification payload construction and disabled search-page cases;
- live verification pending, verified, metadata-mismatch, disabled, and unavailable states.

Keep renderer tests deterministic and offline. Do not make external legal-source requests
from frontend unit tests.

## Focused static check

Regardless of the frontend runner, syntax-check every changed extension script:

```bash
node --check extension/src/background.js
node --check extension/src/content.js
node --check extension/src/popup.js
node --check extension/src/sidepanel.js
```

Report static checks separately from actual frontend test cases.
