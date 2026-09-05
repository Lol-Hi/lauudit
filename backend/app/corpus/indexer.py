from __future__ import annotations

import json
from pathlib import Path

from backend.app.corpus.database import connect, initialize_schema
from backend.app.normalization.case_names import normalize_case_name
from backend.app.normalization.citations import normalize_citation

REQUIRED = {"case_id", "canonical_name", "aliases", "court", "court_code", "decision_date", "source_url", "document_path", "source_type"}


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


def build_index(cases_path: Path, db_path: Path) -> dict:
    errors: list[str] = []
    records: list[dict] = []
    seen_ids: set[str] = set()
    if not cases_path.exists():
        raise FileNotFoundError(f"Corpus metadata not found: {cases_path}")
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
            document = Path(record["document_path"])
            if not document.is_absolute():
                candidates = [cases_path.parent / document]
                if document.as_posix().startswith("data/corpus/"):
                    candidates.append(cases_path.parent.parent.parent / document)
                document = next((candidate for candidate in candidates if candidate.exists()), candidates[0])
            if not document.exists():
                errors.append(f"line {line_number}: document not found {record['document_path']}")
                continue
            record["_document"] = document
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

    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = connect(db_path)
    initialize_schema(connection)
    connection.execute("DELETE FROM paragraph_fts")
    connection.execute("DELETE FROM paragraphs")
    connection.execute("DELETE FROM case_citations")
    connection.execute("DELETE FROM case_aliases")
    connection.execute("DELETE FROM cases")
    for record in records:
        neutral = record.get("neutral_citation")
        connection.execute(
            "INSERT INTO cases VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (record["case_id"], record["canonical_name"], normalize_case_name(record["canonical_name"]), neutral, record["court"], record["court_code"], record["decision_date"], record["source_url"], record["document_path"], record["source_type"]),
        )
        for alias in record["aliases"]:
            connection.execute("INSERT INTO case_aliases VALUES (?, ?, ?)", (record["case_id"], alias, normalize_case_name(alias)))
        citations = ([neutral] if neutral else []) + record.get("reported_citations", [])
        for citation in citations:
            connection.execute("INSERT INTO case_citations VALUES (?, ?, ?, ?)", (record["case_id"], citation, normalize_citation(citation), "neutral" if citation == neutral else "reported"))
        for paragraph_number, paragraph_text in _paragraphs(record["_document"].read_text(encoding="utf-8")):
            connection.execute("INSERT INTO paragraphs VALUES (?, ?, ?)", (record["case_id"], paragraph_number, paragraph_text))
            connection.execute("INSERT INTO paragraph_fts VALUES (?, ?, ?)", (record["case_id"], paragraph_number, paragraph_text))
    connection.commit()
    connection.close()
    return {"records": len(records), "errors": errors, "db_path": str(db_path)}
