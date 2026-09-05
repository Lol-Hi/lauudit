#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.config import settings
from backend.app.corpus.indexer import build_index


if __name__ == "__main__":
    result = build_index(
        settings.absolute_cases_path,
        settings.absolute_db_path,
        completeness=settings.corpus_completeness,
        notes=settings.corpus_notes,
    )
    print(f"Indexed {result['records']} case(s) into {result['db_path']}")
    print(f"Corpus snapshot: {result['snapshot_id']}")
    print(f"Cases metadata SHA-256: {result['cases_sha256']}")
    print(f"Completeness: {result['completeness']}")
    print(f"Build report: {result['report_path']}")
    print("No URLs were fetched; the index uses only locally supplied documents.")
