#!/usr/bin/env python3
"""Manually verify stale corpus source URLs and persist provenance timestamps.

This command is never called by ``POST /api/v1/audit``. It performs one
allowlisted request per eligible case and does not save fetched documents.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.config import settings
from backend.app.maintenance.live_sources import run_live_verification


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify stale allowlisted legal sources")
    parser.add_argument("--cases", type=Path, default=settings.absolute_cases_path)
    parser.add_argument("--db", type=Path, default=settings.absolute_db_path)
    parser.add_argument("--force", action="store_true", help="verify even records checked within the freshness window")
    parser.add_argument("--max-age-days", type=float, default=7.0)
    parser.add_argument("--delay", type=float, default=1.0, help="seconds between eligible source requests")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = run_live_verification(
            args.cases,
            args.db,
            force=args.force,
            max_age_days=args.max_age_days,
            delay_seconds=args.delay,
        )
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        print(f"Live verification aborted: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
