#!/usr/bin/env python3
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.pipeline import run_audit
from backend.app.schemas import AuditRequest


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python scripts/run_benchmark.py data/benchmarks/gold_cases.jsonl")
    path = Path(sys.argv[1])
    passed = total = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        result = run_audit(AuditRequest.model_validate(item))
        actual = result.citations[0].status if result.citations else "NO_CITATIONS"
        total += 1
        passed += actual == item["expected_status"]
        print(f"{'PASS' if actual == item['expected_status'] else 'FAIL'} {item['id']}: {actual} (expected {item['expected_status']})")
    print(f"{passed}/{total} benchmark cases passed")
    raise SystemExit(0 if passed == total else 1)


if __name__ == "__main__":
    main()

