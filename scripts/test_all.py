#!/usr/bin/env python3
"""Run Lauudit's local verification workflow and return one aggregate status."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
BENCHMARKS = (
    ROOT / "data/benchmarks/gold_cases.jsonl",
    ROOT / "data/benchmarks/adversarial_cases.jsonl",
)
JS_FILES = (
    ROOT / "extension/src/background.js",
    ROOT / "extension/src/content.js",
    ROOT / "extension/src/popup-model.js",
    ROOT / "extension/src/popup.js",
)


@dataclass
class StepResult:
    label: str
    passed: bool
    summary: str
    output: str = ""


def python_executable() -> str:
    """Prefer the repository virtualenv, while keeping direct Python usable."""

    candidate = ROOT / ".venv/bin/python"
    return str(candidate) if candidate.is_file() else sys.executable


def run_process(label: str, command: Sequence[str], *, env: dict[str, str] | None = None) -> StepResult:
    try:
        completed = subprocess.run(
            list(command),
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
    except OSError as exc:
        return StepResult(label, False, f"could not start command: {exc}")

    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
    if completed.returncode:
        return StepResult(label, False, f"command exited with {completed.returncode}", output)
    return StepResult(label, True, summarize(label, output), output)


def summarize(label: str, output: str) -> str:
    if label == "Corpus index":
        match = re.search(r"Indexed (\d+) case\(s\)", output)
        return f"{match.group(1)} case(s) indexed" if match else "completed"
    if label == "Backend tests":
        match = re.search(r"(\d+) passed", output)
        return f"{match.group(1)} passed" if match else "completed"
    if label == "Frontend tests":
        match = re.search(r"Tests\s+(\d+) passed", output)
        return f"{match.group(1)} passed" if match else "completed"
    if label.endswith("benchmark"):
        match = re.search(r"(\d+)/(\d+) benchmark cases passed", output)
        return f"{match.group(1)}/{match.group(2)} passed" if match else "completed"
    return "completed"


def validate_manifest() -> StepResult:
    label = "Manifest JSON"
    path = ROOT / "extension/manifest.json"
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return StepResult(label, False, str(exc))
    return StepResult(label, True, "valid")


def check_javascript(node: str) -> StepResult:
    label = "Extension syntax"
    failures: list[str] = []
    for path in JS_FILES:
        result = run_process(path.name, [node, "--check", str(path)])
        if not result.passed:
            failures.append(f"{path.relative_to(ROOT)}: {result.summary}")
    if failures:
        return StepResult(label, False, "; ".join(failures))
    return StepResult(label, True, f"{len(JS_FILES)} files checked")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Lauudit's local test and verification suite")
    parser.add_argument(
        "--skip-benchmarks",
        action="store_true",
        help="skip the gold and adversarial benchmark cases",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runner = python_executable()
    results: list[StepResult] = []

    results.append(run_process("Corpus index", [runner, "scripts/build_index.py"]))
    results.append(run_process("Backend tests", [runner, "-m", "pytest", "-q"]))

    if args.skip_benchmarks:
        print("[SKIP] Benchmarks: skipped by request")
    else:
        benchmark_env = os.environ.copy()
        benchmark_env["ENABLE_LIVE_VERIFICATION"] = "false"
        for benchmark in BENCHMARKS:
            label = "Gold benchmark" if benchmark.name == "gold_cases.jsonl" else "Adversarial benchmark"
            results.append(
                run_process(
                    label,
                    [runner, "scripts/run_benchmark.py", str(benchmark)],
                    env=benchmark_env,
                )
            )

    node = shutil.which("node")
    if node:
        results.append(check_javascript(node))
    else:
        results.append(StepResult("Extension syntax", False, "node executable not found"))

    frontend_package = ROOT / "extension/package.json"
    npm = shutil.which("npm")
    if frontend_package.is_file() and npm:
        results.append(run_process("Frontend tests", [npm, "--prefix", "extension", "test"]))
    elif frontend_package.is_file():
        results.append(StepResult("Frontend tests", False, "npm executable not found"))
    else:
        print("[SKIP] Frontend tests: no frontend test suite configured")

    results.append(validate_manifest())

    for result in results:
        print(f"[{('PASS' if result.passed else 'FAIL')}] {result.label}: {result.summary}")
        if not result.passed and result.output:
            print(result.output)

    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
