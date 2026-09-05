---
name: lauudit-testing
description: Run and interpret Lauudit's backend, corpus, benchmark, frontend, and browser/API integration verification workflows.
metadata:
  short-description: Run and interpret Lauudit verification
---

# Lauudit Testing

Use this skill when changing Lauudit backend code, corpus data, benchmark cases,
test files, scripts, or Chrome extension files. It covers the committed backend
workflow, frontend unit tests when present, and browser/API integration tests
when present.

## Default workflow

Work from the repository root and run the committed verification entry point:

```bash
.venv/bin/python scripts/test_all.py
```

It rebuilds the corpus index, runs the backend pytest suite, executes the gold
and adversarial benchmarks, checks extension JavaScript syntax, and validates
the extension manifest. Treat a non-zero exit code as a failed verification.

After the centralized workflow, discover and run additional frontend and
integration suites when the repository provides them. Read the relevant guide
before running each kind of suite:

- [Frontend testing](references/frontend-testing.md) for renderer, DOM, and
  extension-message unit tests.
- [Integration testing](references/integration-testing.md) for FastAPI HTTP,
  browser-extension, and end-to-end checks.

Do not describe JavaScript syntax checks as a frontend test suite. If no
frontend or integration suite exists, report that explicitly as a coverage gap
and still run the available static/backend workflow.

If the virtual environment or dependencies are missing, report that as an
environment setup failure rather than replacing the project workflow with
ad-hoc test commands.

## Focused iteration

Use targeted checks when the change is narrow, then run the full workflow before
handing off the work:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python scripts/build_index.py
.venv/bin/python scripts/test_all.py --skip-benchmarks
```

Rebuild the index whenever files under `data/corpus/` change. Run the full
workflow whenever benchmark cases, backend behavior, or extension files change.

For frontend-only changes, run the repository's declared frontend test command
if one exists, then run `node --check` on every changed extension script. For
integration changes, use the repository's declared integration command or the
documented browser harness; do not start a live server for ordinary unit tests.
Do not invent `npm`, Playwright, or browser commands when their configuration
is absent.

## Failure interpretation

- Investigate corpus index failures before benchmark failures because the
  benchmarks depend on the generated index.
- Read `docs/evaluation-methodology.md` when interpreting benchmark regressions.
- `NOT_FOUND_IN_VERIFIED_CORPUS` means the case is absent from the local verified
  corpus; it does not establish that the case is legally nonexistent.
- Do not start Uvicorn for ordinary API tests. The FastAPI `TestClient` tests
  exercise the API in-process; use a live server only when explicitly testing
  HTTP or extension integration.
- Keep deterministic integration tests offline where possible. Stub or mock
  external legal-source responses rather than making uncontrolled live requests.
- Treat browser-launch, dependency, display, and server-start failures as
  environment/setup failures unless the test itself reports an application
  assertion failure.
- Distinguish dependency or tool availability failures from code failures in
  the final report.

## Reporting

Report the exact command run, each pass/fail/skip category, relevant failure
output, and the next recommended debugging step. Separate backend, frontend,
and integration coverage in the report. Preserve unrelated working-tree changes
and do not commit unless the user explicitly asks for a commit.
