import hashlib
import json
from pathlib import Path

import pytest

from backend.app.corpus.database import connect, current_corpus
from backend.app.corpus.indexer import build_index


def _make_corpus(root: Path, source_url: str = "https://official.test/case-1") -> tuple[Path, Path]:
    corpus = root / "corpus"
    documents = corpus / "documents"
    documents.mkdir(parents=True)
    document = documents / "case.txt"
    document.write_text("[42] The court held that the agreement was objectively formed.\n", encoding="utf-8")
    cases = corpus / "cases.jsonl"
    cases.write_text(
        json.dumps(
            {
                "case_id": "case-1",
                "canonical_name": "Lim v Tan",
                "aliases": ["Tan v Lim"],
                "neutral_citation": "[2023] SGCA 12",
                "reported_citations": [],
                "court": "Court of Appeal",
                "court_code": "SGCA",
                "decision_date": "2023-01-01",
                "source_url": source_url,
                "document_path": "documents/case.txt",
                "source_type": "test",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return cases, document


def test_snapshot_is_content_derived_and_records_document_hash(indexed_db):
    connection = connect(indexed_db)
    corpus = current_corpus(connection)
    provenance = connection.execute("SELECT * FROM case_provenance").fetchone()
    connection.close()

    assert corpus is not None
    assert corpus["snapshot_id"].startswith("snapshot-")
    assert corpus["completeness"] == "partial"
    assert len(corpus["cases_sha256"]) == 64
    assert len(provenance["document_sha256"]) == 64
    assert provenance["document_size_bytes"] > 0


def test_rebuild_failure_does_not_replace_existing_index(indexed_db, tmp_path: Path):
    broken_cases = tmp_path / "broken-cases.jsonl"
    broken_cases.write_text(
        '{"case_id":"broken","canonical_name":"Broken v Case","aliases":[],"neutral_citation":"[2023] SGHC 99",'
        '"court":"Court","court_code":"SGHC",'
        '"decision_date":"2023-01-01","source_url":"https://example.test/broken",'
        '"document_path":"missing.txt","source_type":"test"}\n',
        encoding="utf-8",
    )

    try:
        build_index(broken_cases, indexed_db)
    except ValueError as exc:
        assert "document not found" in str(exc)
    else:
        raise AssertionError("expected the broken corpus build to fail")

    connection = connect(indexed_db)
    assert connection.execute("SELECT COUNT(*) FROM cases").fetchone()[0] == 1
    assert current_corpus(connection) is not None
    connection.close()


def test_identical_inputs_produce_the_same_snapshot_id(tmp_path: Path):
    cases, _ = _make_corpus(tmp_path)
    first = build_index(cases, tmp_path / "first.sqlite3")
    second = build_index(cases, tmp_path / "second.sqlite3")

    assert first["snapshot_id"] == second["snapshot_id"]
    assert first["cases_sha256"] == second["cases_sha256"]


def test_document_change_produces_a_new_snapshot_and_hash(tmp_path: Path):
    cases, document = _make_corpus(tmp_path)
    first = build_index(cases, tmp_path / "first.sqlite3")
    first_hash = hashlib.sha256(document.read_bytes()).hexdigest()

    document.write_text("[42] The court held a materially different proposition.\n", encoding="utf-8")
    second = build_index(cases, tmp_path / "second.sqlite3")
    connection = connect(tmp_path / "second.sqlite3")
    second_hash = connection.execute("SELECT document_sha256 FROM case_provenance").fetchone()[0]
    connection.close()

    assert first["snapshot_id"] != second["snapshot_id"]
    assert first_hash != second_hash
    assert second_hash == hashlib.sha256(document.read_bytes()).hexdigest()


def test_metadata_change_produces_a_new_snapshot_and_metadata_hash(tmp_path: Path):
    cases, _ = _make_corpus(tmp_path)
    first = build_index(cases, tmp_path / "first.sqlite3")

    record = json.loads(cases.read_text(encoding="utf-8"))
    record["source_url"] = "https://www.elitigation.sg/Documents/case-1.pdf"
    cases.write_text(json.dumps(record) + "\n", encoding="utf-8")
    second = build_index(cases, tmp_path / "second.sqlite3")

    assert first["snapshot_id"] != second["snapshot_id"]
    assert first["cases_sha256"] != second["cases_sha256"]


def test_custom_completeness_and_notes_are_persisted(tmp_path: Path):
    cases, _ = _make_corpus(tmp_path)
    build_index(
        cases,
        tmp_path / "index.sqlite3",
        completeness="comprehensive",
        notes="Supreme Court judgments within the documented 2000-2025 collection scope.",
    )
    connection = connect(tmp_path / "index.sqlite3")
    corpus = current_corpus(connection)
    connection.close()

    assert corpus["completeness"] == "comprehensive"
    assert corpus["notes"].startswith("Supreme Court judgments")


def test_source_verification_metadata_and_build_report_are_persisted(tmp_path: Path):
    cases, _ = _make_corpus(tmp_path)
    record = json.loads(cases.read_text(encoding="utf-8"))
    record["source_verified"] = True
    record["retrieved_at"] = "2026-09-05T10:30:00+08:00"
    cases.write_text(json.dumps(record) + "\n", encoding="utf-8")

    result = build_index(cases, tmp_path / "index.sqlite3")
    connection = connect(tmp_path / "index.sqlite3")
    provenance = connection.execute(
        "SELECT source_verified, retrieved_at FROM case_provenance"
    ).fetchone()
    connection.close()
    report = json.loads(Path(result["report_path"]).read_text(encoding="utf-8"))

    assert provenance["source_verified"] == 1
    assert provenance["retrieved_at"] == "2026-09-05T10:30:00+08:00"
    assert report["snapshot_id"] == result["snapshot_id"]
    assert report["offline_build"] is True
    assert report["record_count"] == 1


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("decision_date", "2023-02-30", "decision_date must be a valid"),
        ("decision_date", "2023/01/01", "decision_date must be a valid"),
        ("source_url", "", "source_url must not be blank"),
        ("source_url", "ftp://official.test/case-1", "malformed source_url"),
        ("retrieved_at", "2026-09-05 10:30:00", "retrieved_at must be an ISO-8601"),
    ],
)
def test_invalid_provenance_fields_are_rejected(
    tmp_path: Path,
    field: str,
    value: str,
    message: str,
):
    cases, _ = _make_corpus(tmp_path)
    record = json.loads(cases.read_text(encoding="utf-8"))
    record[field] = value
    cases.write_text(json.dumps(record) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        build_index(cases, tmp_path / "index.sqlite3")


def test_duplicate_canonical_names_and_aliases_are_rejected(tmp_path: Path):
    cases, document = _make_corpus(tmp_path)
    second_document = document.parent / "second.txt"
    second_document.write_text("[1] Another judgment.\n", encoding="utf-8")
    records = [json.loads(line) for line in cases.read_text(encoding="utf-8").splitlines()]
    records.append(
        {
            **records[0],
            "case_id": "case-2",
            "document_path": "documents/second.txt",
            "neutral_citation": "[2023] SGCA 13",
            "canonical_name": "Different v Case",
            "aliases": ["Lim v Tan"],
        }
    )
    cases.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate canonical name/alias"):
        build_index(cases, tmp_path / "index.sqlite3")


def test_unreachable_source_url_is_metadata_only(tmp_path: Path):
    cases, _ = _make_corpus(tmp_path, "https://unreachable.invalid/judgment.pdf")
    result = build_index(cases, tmp_path / "index.sqlite3")
    connection = connect(tmp_path / "index.sqlite3")
    provenance = connection.execute("SELECT source_url FROM case_provenance").fetchone()[0]
    connection.close()

    assert result["records"] == 1
    assert provenance == "https://unreachable.invalid/judgment.pdf"


def test_invalid_completeness_is_rejected_before_creating_an_index(tmp_path: Path):
    cases, _ = _make_corpus(tmp_path)
    with pytest.raises(ValueError, match="completeness must be one of"):
        build_index(cases, tmp_path / "index.sqlite3", completeness="guessed")
    assert not (tmp_path / "index.sqlite3").exists()
