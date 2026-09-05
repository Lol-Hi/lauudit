from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.corpus.database import connect, initialize_schema
from backend.app.normalization.case_names import normalize_case_name
from backend.app.normalization.citations import normalize_citation

REQUIRED = {
    "case_id",
    "canonical_name",
    "aliases",
    "court",
    "court_code",
    "decision_date",
    "source_url",
    "document_path",
    "source_type",
}
DEFAULT_CORPUS_NOTES = "Locally prepared permitted judgments; not a comprehensive Singapore case database."


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _paragraphs(text: str) -> list[tuple[int, str]]:
    blocks = [block.strip() for block in text.replace("\r\n", "\n").split("\n\n") if block.strip()]
    output = []
    for index, block in enumerate(blocks, 1):
        first_line = block.splitlines()[0]
        number = index
        if first_line.startswith("[") and "]" in first_line:
            try:
                number = int(first_line[1 : first_line.index("]")])
            except ValueError:
                pass
        output.append((number, block))
    return output


def _resolve_document(cases_path: Path, value: str) -> Path:
    document = Path(value)
    if document.is_absolute():
        return document
    candidates = [cases_path.parent / document]
    if str(document).startswith("data/corpus/"):
        candidates.append(cases_path.parent.parent.parent / document)
    return next((candidate for candidate in candidates if candidate.exists()), candidates[0])


def _snapshot_id(cases_sha256: str, records: list[dict[str, Any]]) -> str:
    manifest = [
        {
            "case_id": record["case_id"],
            "document_sha256": record["_document_sha256"],
            "source_url": record["source_url"],
            "source_type": record["source_type"],
        }
        for record in sorted(records, key=lambda item: item["case_id"])
    ]
    payload = json.dumps(
        {"cases_sha256": cases_sha256, "records": manifest},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"snapshot-{hashlib.sha256(payload).hexdigest()[:16]}"


def build_index(
    cases_path: Path,
    db_path: Path,
    *,
    completeness: str = "partial",
    notes: str = DEFAULT_CORPUS_NOTES,
) -> dict[str, Any]:
    """Validate and atomically build a corpus index from local files.

    This function deliberately does not fetch URLs. ``source_url`` is retained
    as provenance for a judgment that the team has already obtained and is
    permitted to index.
    """
    if completeness not in {"partial", "comprehensive", "unknown"}:
        raise ValueError("completeness must be one of: partial, comprehensive, unknown")

    errors: list[str] = []
    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    if not cases_path.exists():
        raise FileNotFoundError(f"Corpus metadata not found: {cases_path}")
    cases_sha256 = _sha256(cases_path)
    with cases_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_number}: invalid JSON ({exc.msg})")
                continue
            missing = REQUIRED - set(record)
            if missing:
                errors.append(f"line {line_number}: missing fields {sorted(missing)}")
                continue
            if record["case_id"] in seen_ids:
                errors.append(f"line {line_number}: duplicate case_id {record['case_id']}")
                continue
            seen_ids.add(record["case_id"])
            if not isinstance(record["aliases"], list) or not all(isinstance(a, str) for a in record["aliases"]):
                errors.append(f"line {line_number}: aliases must be a list of strings")
                continue
            if not record.get("neutral_citation") and not record.get("reported_citations"):
                errors.append(f"line {line_number}: at least one neutral_citation or reported_citations entry is required")
                continue
            if record.get("reported_citations") is not None and (
                not isinstance(record.get("reported_citations"), list)
                or not all(isinstance(citation, str) for citation in record.get("reported_citations", []))
            ):
                errors.append(f"line {line_number}: reported_citations must be a list of strings")
                continue
            document = _resolve_document(cases_path, record["document_path"])
            if not document.exists():
                errors.append(f"line {line_number}: document not found {record['document_path']}")
                continue
            record["_document"] = document
            record["_document_sha256"] = _sha256(document)
            record["_document_size_bytes"] = document.stat().st_size
            records.append(record)

    citation_owners: dict[str, str] = {}
    for record in records:
        citations = ([record.get("neutral_citation")] if record.get("neutral_citation") else []) + record.get("reported_citations", [])
        for citation in citations:
            normalized = normalize_citation(citation)
            previous = citation_owners.get(normalized)
            if previous and previous != record["case_id"]:
                errors.append(f"duplicate citation {citation!r} used by {previous} and {record['case_id']}")
            citation_owners[normalized] = record["case_id"]

    if errors:
        raise ValueError("\n".join(errors))

    snapshot_id = _snapshot_id(cases_sha256, records)
    created_at = datetime.now(timezone.utc).isoformat()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    temp_db_path = db_path.with_name(f".{db_path.name}.{uuid.uuid4().hex}.tmp")
    connection = None
    try:
        connection = connect(temp_db_path)
        initialize_schema(connection)
        for record in records:
            neutral = record.get("neutral_citation")
            connection.execute(
                "INSERT INTO cases VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record["case_id"],
                    record["canonical_name"],
                    normalize_case_name(record["canonical_name"]),
                    neutral,
                    record["court"],
                    record["court_code"],
                    record["decision_date"],
                    record["source_url"],
                    record["document_path"],
                    record["source_type"],
                ),
            )
            for alias in record["aliases"]:
                connection.execute("INSERT INTO case_aliases VALUES (?, ?, ?)", (record["case_id"], alias, normalize_case_name(alias)))
            citations = ([neutral] if neutral else []) + record.get("reported_citations", [])
            for citation in citations:
                connection.execute(
                    "INSERT INTO case_citations VALUES (?, ?, ?, ?)",
                    (record["case_id"], citation, normalize_citation(citation), "neutral" if citation == neutral else "reported"),
                )
            for paragraph_number, paragraph_text in _paragraphs(record["_document"].read_text(encoding="utf-8")):
                connection.execute("INSERT INTO paragraphs VALUES (?, ?, ?)", (record["case_id"], paragraph_number, paragraph_text))
                connection.execute("INSERT INTO paragraph_fts VALUES (?, ?, ?)", (record["case_id"], paragraph_number, paragraph_text))

        connection.execute(
            "INSERT INTO corpus_snapshots VALUES (?, ?, ?, ?, ?, ?, ?)",
            (snapshot_id, str(cases_path), cases_sha256, created_at, completeness, notes, len(records)),
        )
        for record in records:
            connection.execute(
                "INSERT INTO case_provenance VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    snapshot_id,
                    record["case_id"],
                    record["document_path"],
                    record["_document_sha256"],
                    record["_document_size_bytes"],
                    record["source_url"],
                    record["source_type"],
                ),
            )
        connection.execute("INSERT INTO corpus_state VALUES ('current_snapshot_id', ?)", (snapshot_id,))
        connection.commit()
        connection.close()
        connection = None
        os.replace(temp_db_path, db_path)
    finally:
        if connection is not None:
            connection.close()
        if temp_db_path.exists():
            temp_db_path.unlink()

    return {
        "records": len(records),
        "errors": errors,
        "db_path": str(db_path),
        "snapshot_id": snapshot_id,
        "cases_sha256": cases_sha256,
        "completeness": completeness,
        "document_files": len(records),
    }
