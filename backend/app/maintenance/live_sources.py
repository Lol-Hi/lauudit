"""Batch live-source verification for an explicit maintenance run.

This module is intentionally not imported by the audit pipeline. It reads the
curated JSONL manifest, calls the isolated live verifier one case at a time,
and persists only verification state into the active corpus provenance table.
Fetched pages and PDFs are never written to the repository or the corpus.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from backend.app.corpus.database import connect, current_corpus, initialize_schema
from backend.app.verifiers.live_source import LiveVerificationResult, verify_live_source


@dataclass(frozen=True)
class MaintenanceReport:
    snapshot_id: Optional[str]
    considered: int
    verified: int
    mismatched: int
    unavailable: int
    skipped_fresh: int
    skipped_unattempted: int
    missing_provenance: int
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_timestamp(value: object) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _is_fresh(retrieved_at: object, *, now: datetime, max_age: timedelta) -> bool:
    parsed = _parse_timestamp(retrieved_at)
    return parsed is not None and now - parsed <= max_age


def _load_records(cases_path: Path) -> Iterable[dict[str, Any]]:
    with cases_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"line {line_number}: invalid JSON ({exc.msg})") from exc
            if not isinstance(record, dict):
                raise ValueError(f"line {line_number}: each record must be a JSON object")
            yield record


def _expected_metadata(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: record[key]
        for key in ("canonical_name", "neutral_citation", "court", "court_code", "decision_date")
        if record.get(key) is not None
    }


def _persist_result(
    connection: Any,
    snapshot_id: str,
    case_id: str,
    result: LiveVerificationResult,
) -> bool:
    updated = connection.execute(
        """
        UPDATE case_provenance
        SET source_verified = ?, retrieved_at = ?
        WHERE snapshot_id = ? AND case_id = ?
        """,
        (int(result.source_verified), result.retrieved_at, snapshot_id, case_id),
    ).rowcount
    return updated == 1


def run_live_verification(
    cases_path: Path,
    db_path: Path,
    *,
    force: bool = False,
    max_age_days: float = 7.0,
    delay_seconds: float = 1.0,
    now: Optional[datetime] = None,
    verifier: Callable[[str, dict[str, Any]], LiveVerificationResult] = verify_live_source,
) -> MaintenanceReport:
    """Verify stale corpus records and persist only their provenance state.

    ``verifier`` is injectable so tests never need network access. A case with
    an untrusted/search URL is counted as skipped and does not overwrite an
    existing verification timestamp. HTTP failures and metadata mismatches are
    attempted results and are persisted, so a later run can make an explicit
    decision about re-verification.
    """
    if max_age_days < 0:
        raise ValueError("max_age_days must be non-negative")
    if delay_seconds < 0:
        raise ValueError("delay_seconds must be non-negative")
    if not cases_path.exists():
        raise FileNotFoundError(f"Corpus metadata not found: {cases_path}")
    if not db_path.exists():
        raise FileNotFoundError(f"Corpus index not found: {db_path}")

    run_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    max_age = timedelta(days=max_age_days)
    connection = connect(db_path)
    initialize_schema(connection)
    corpus = current_corpus(connection)
    if not corpus:
        connection.close()
        raise ValueError("The corpus index has no current snapshot")

    snapshot_id = corpus["snapshot_id"]
    considered = verified = mismatched = unavailable = 0
    skipped_fresh = skipped_unattempted = missing_provenance = 0
    errors: list[str] = []
    try:
        records = list(_load_records(cases_path))
        for record_index, record in enumerate(records):
            case_id = record.get("case_id")
            if not isinstance(case_id, str) or not case_id:
                errors.append("record without a valid case_id")
                continue
            provenance = connection.execute(
                "SELECT source_verified, retrieved_at FROM case_provenance WHERE snapshot_id = ? AND case_id = ?",
                (snapshot_id, case_id),
            ).fetchone()
            if provenance is None:
                missing_provenance += 1
                errors.append(f"{case_id}: no provenance row in current snapshot")
                continue
            if not force and _is_fresh(provenance["retrieved_at"], now=run_at, max_age=max_age):
                skipped_fresh += 1
                continue

            considered += 1
            result = verifier(record["source_url"], _expected_metadata(record))
            if result.status == "LIVE_ACCESS_BLOCKED":
                raise RuntimeError(f"{case_id}: {result.reason}")
            if not result.attempted:
                skipped_unattempted += 1
                continue
            if not _persist_result(connection, snapshot_id, case_id, result):
                errors.append(f"{case_id}: provenance update affected no rows")
                continue
            if result.status == "LIVE_VERIFIED":
                verified += 1
            elif result.status == "LIVE_METADATA_MISMATCH":
                mismatched += 1
            else:
                unavailable += 1
            if delay_seconds and record_index < len(records) - 1:
                time.sleep(delay_seconds)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    return MaintenanceReport(
        snapshot_id=snapshot_id,
        considered=considered,
        verified=verified,
        mismatched=mismatched,
        unavailable=unavailable,
        skipped_fresh=skipped_fresh,
        skipped_unattempted=skipped_unattempted,
        missing_provenance=missing_provenance,
        errors=tuple(errors),
    )
