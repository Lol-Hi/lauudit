---
name: lauudit-testing
description: Run and interpret Lauudit's centralized backend, corpus, benchmark, and extension verification workflow.
metadata:
  short-description: Run and interpret Lauudit verification
---

# Lauudit Testing

Use this skill when changing Lauudit backend code, corpus data, benchmark cases,
test files, scripts, or Chrome extension files.

## Default workflow

Work from the repository root and run the committed verification entry point:

```bash
.venv/bin/python scripts/test_all.py
```

It rebuilds the corpus index, runs the backend pytest suite, executes the gold
and adversarial benchmarks, checks extension JavaScript syntax, and validates
the extension manifest. Treat a non-zero exit code as a failed verification.

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

## Failure interpretation

- Investigate corpus index failures before benchmark failures because the
  benchmarks depend on the generated index.
- Read `docs/evaluation-methodology.md` when interpreting benchmark regressions.
- `NOT_FOUND_IN_VERIFIED_CORPUS` means the case is absent from the local verified
  corpus; it does not establish that the case is legally nonexistent.
- Do not start Uvicorn for ordinary API tests. The FastAPI `TestClient` tests
  exercise the API in-process; use a live server only when explicitly testing
  HTTP or extension integration.
- Distinguish dependency or tool availability failures from code failures in
  the final report.

## Reporting

Report the exact command run, each pass/fail category, relevant failure output,
and the next recommended debugging step. Preserve unrelated working-tree
changes and do not commit unless the user explicitly asks for a commit.
