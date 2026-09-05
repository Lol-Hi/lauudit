from pathlib import Path

from backend.app.corpus.database import connect, current_corpus
from backend.app.corpus.indexer import build_index


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
