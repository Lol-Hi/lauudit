from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional


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
        CREATE TABLE IF NOT EXISTS corpus_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            cases_path TEXT NOT NULL,
            cases_sha256 TEXT NOT NULL,
            created_at TEXT NOT NULL,
            completeness TEXT NOT NULL,
            notes TEXT NOT NULL,
            record_count INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS case_provenance (
            snapshot_id TEXT NOT NULL REFERENCES corpus_snapshots(snapshot_id) ON DELETE CASCADE,
            case_id TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
            document_path TEXT NOT NULL,
            document_sha256 TEXT NOT NULL,
            document_size_bytes INTEGER NOT NULL,
            source_url TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_verified INTEGER NOT NULL DEFAULT 0,
            retrieved_at TEXT,
            PRIMARY KEY (snapshot_id, case_id)
        );
        CREATE TABLE IF NOT EXISTS corpus_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )
    _ensure_column(connection, "case_provenance", "source_verified", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(connection, "case_provenance", "retrieved_at", "TEXT")


def _ensure_column(
    connection: sqlite3.Connection,
    table: str,
    column: str,
    definition: str,
) -> None:
    columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def current_corpus(connection: sqlite3.Connection) -> Optional[dict[str, str]]:
    """Return the metadata for the index currently used by the audit service."""
    row = connection.execute(
        """
        SELECT s.*
        FROM corpus_state state
        JOIN corpus_snapshots s ON s.snapshot_id = state.value
        WHERE state.key = 'current_snapshot_id'
        """
    ).fetchone()
    return dict(row) if row else None
