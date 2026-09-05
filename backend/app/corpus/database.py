from __future__ import annotations

import sqlite3
from pathlib import Path


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS cases (
            case_id TEXT PRIMARY KEY,
            canonical_name TEXT NOT NULL,
            normalized_name TEXT NOT NULL,
            neutral_citation TEXT,
            court TEXT NOT NULL,
            court_code TEXT NOT NULL,
            decision_date TEXT NOT NULL,
            source_url TEXT NOT NULL,
            document_path TEXT NOT NULL,
            source_type TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS case_aliases (
            case_id TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
            alias TEXT NOT NULL,
            normalized_alias TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS case_citations (
            case_id TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
            citation TEXT NOT NULL,
            normalized_citation TEXT NOT NULL,
            citation_type TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS paragraphs (
            case_id TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
            paragraph_number INTEGER NOT NULL,
            text TEXT NOT NULL,
            PRIMARY KEY (case_id, paragraph_number)
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS paragraph_fts USING fts5(
            case_id UNINDEXED, paragraph_number UNINDEXED, text
        );
        CREATE INDEX IF NOT EXISTS idx_case_citations_normalized ON case_citations(normalized_citation);
        CREATE INDEX IF NOT EXISTS idx_case_aliases_normalized ON case_aliases(normalized_alias);
        """
    )

