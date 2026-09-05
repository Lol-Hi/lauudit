#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.pipeline import run_audit
from backend.app.schemas import AuditRequest


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit a JSON request or response text locally")
    parser.add_argument("input", help="JSON file containing an AuditRequest")
    args = parser.parse_args()
    payload = json.loads(open(args.input, encoding="utf-8").read())
    print(run_audit(AuditRequest.model_validate(payload)).model_dump_json(indent=2))


if __name__ == "__main__":
    main()
