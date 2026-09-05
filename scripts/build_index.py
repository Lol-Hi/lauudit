#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.config import settings
from backend.app.corpus.indexer import build_index


if __name__ == "__main__":
    result = build_index(settings.absolute_cases_path, settings.absolute_db_path)
    print(f"Indexed {result['records']} case(s) into {result['db_path']}")
