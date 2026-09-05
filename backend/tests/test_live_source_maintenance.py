from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.app.corpus.database import connect, current_corpus
from backend.app.maintenance.live_sources import run_live_verification
from backend.app.verifiers.live_source import LiveVerificationResult


def _set_retrieved_at(db: Path, value: Optional[str]) -> None:
    connection = connect(db)
    snapshot_id = current_corpus(connection)["snapshot_id"]
    connection.execute(
        "UPDATE case_provenance SET source_verified = 0, retrieved_at = ? WHERE snapshot_id = ? AND case_id = ?",
        (value, snapshot_id, "case-1"),
    )
    connection.commit()
    connection.close()


def _verified(source_url: str, expected: dict) -> LiveVerificationResult:
    return LiveVerificationResult(
        status="LIVE_VERIFIED",
        attempted=True,
        source_verified=True,
        final_url=source_url,
        retrieved_at="2026-09-06T02:00:00+00:00",
        metadata_match={key: True for key in expected if key in {"canonical_name", "neutral_citation", "court", "court_code", "decision_date"}},
    )


def test_maintenance_persists_attempted_result_without_fetching_documents(indexed_db, tmp_path):
    calls = []
    cases = tmp_path / "corpus/cases.jsonl"
    cases.parent.mkdir(parents=True, exist_ok=True)
    cases.write_text(
        '{"case_id":"case-1","canonical_name":"Lim v Tan","neutral_citation":"[2023] SGCA 12",'
        '"court":"Court of Appeal","court_code":"SGCA","decision_date":"2023-01-01",'
        '"source_url":"https://www.elitigation.sg/gdviewer/s/2023_SGCA_12"}\n',
        encoding="utf-8",
    )

    def verifier(source_url, expected):
        calls.append((source_url, expected))
        return _verified(source_url, expected)

    report = run_live_verification(cases, indexed_db, delay_seconds=0, verifier=verifier)

    assert report.verified == 1
    assert report.skipped_fresh == 0
    assert calls[0][0].startswith("https://www.elitigation.sg/")
    connection = connect(indexed_db)
    row = connection.execute("SELECT source_verified, retrieved_at FROM case_provenance").fetchone()
    connection.close()
    assert row["source_verified"] == 1
    assert row["retrieved_at"] == "2026-09-06T02:00:00+00:00"


def test_maintenance_skips_fresh_records_unless_forced(indexed_db, tmp_path):
    cases = tmp_path / "cases.jsonl"
    cases.write_text(
        '{"case_id":"case-1","canonical_name":"Lim v Tan","source_url":"https://www.elitigation.sg/case"}\n',
        encoding="utf-8",
    )
    _set_retrieved_at(indexed_db, "2026-09-05T12:00:00+00:00")
    calls = []

    def verifier(source_url, expected):
        calls.append(source_url)
        return _verified(source_url, expected)

    now = datetime(2026, 9, 6, 0, 0, tzinfo=timezone.utc)
    report = run_live_verification(cases, indexed_db, now=now, delay_seconds=0, verifier=verifier)
    assert report.skipped_fresh == 1
    assert calls == []

    forced = run_live_verification(cases, indexed_db, force=True, now=now, delay_seconds=0, verifier=verifier)
    assert forced.verified == 1
    assert len(calls) == 1


def test_maintenance_does_not_persist_unattempted_source(indexed_db, tmp_path):
    cases = tmp_path / "cases.jsonl"
    cases.write_text(
        '{"case_id":"case-1","canonical_name":"Lim v Tan","source_url":"https://example.com/case"}\n',
        encoding="utf-8",
    )
    _set_retrieved_at(indexed_db, None)

    report = run_live_verification(
        cases,
        indexed_db,
        delay_seconds=0,
        verifier=lambda source_url, expected: LiveVerificationResult(
            status="LIVE_VERIFICATION_SKIPPED_UNTRUSTED_HOST",
            attempted=False,
            source_verified=False,
            retrieved_at=None,
        ),
    )

    assert report.skipped_unattempted == 1
    connection = connect(indexed_db)
    row = connection.execute("SELECT source_verified, retrieved_at FROM case_provenance").fetchone()
    connection.close()
    assert row["source_verified"] == 0
    assert row["retrieved_at"] is None


def test_maintenance_aborts_and_rolls_back_when_a_source_blocks_access(indexed_db, tmp_path):
    cases = tmp_path / "cases.jsonl"
    cases.write_text(
        '{"case_id":"case-1","canonical_name":"Lim v Tan","source_url":"https://www.elitigation.sg/case"}\n',
        encoding="utf-8",
    )

    def blocked(source_url, expected):
        return LiveVerificationResult(
            status="LIVE_ACCESS_BLOCKED",
            attempted=True,
            source_verified=False,
            retrieved_at="2026-09-06T02:00:00+00:00",
            reason="CAPTCHA detected",
        )

    import pytest

    with pytest.raises(RuntimeError, match="CAPTCHA detected"):
        run_live_verification(cases, indexed_db, delay_seconds=0, verifier=blocked)

    connection = connect(indexed_db)
    row = connection.execute("SELECT source_verified, retrieved_at FROM case_provenance").fetchone()
    connection.close()
    assert row["source_verified"] == 0
    assert row["retrieved_at"] is None
