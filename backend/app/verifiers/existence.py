from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import List, Optional

from backend.app.corpus import search


@dataclass
class ExistenceResult:
    status: str
    case: Optional[dict] = None
    candidates: Optional[List[dict]] = None
    method: str = "none"


def verify_existence(connection: sqlite3.Connection, provided_name: Optional[str], provided_citation: Optional[str]) -> ExistenceResult:
    if provided_citation:
        candidates = search.by_citation(connection, provided_citation)
        if len(candidates) == 1:
            return ExistenceResult("VERIFIED_EXISTS", candidates[0], method="exact_citation")
        if len(candidates) > 1:
            return ExistenceResult("AMBIGUOUS_MATCH", candidates=candidates, method="duplicate_citation")
    if provided_name:
        candidates = search.by_exact_name(connection, provided_name)
        if len(candidates) == 1:
            return ExistenceResult("VERIFIED_EXISTS", candidates[0], method="exact_name")
        if len(candidates) > 1:
            return ExistenceResult("AMBIGUOUS_MATCH", candidates=candidates, method="exact_name_multiple")
        candidates = search.fuzzy_names(connection, provided_name)
        if len(candidates) == 1:
            return ExistenceResult("VERIFIED_EXISTS", candidates[0], candidates=candidates, method="fuzzy_name")
        if len(candidates) > 1:
            return ExistenceResult("AMBIGUOUS_MATCH", candidates=candidates, method="fuzzy_name_multiple")
    return ExistenceResult("NOT_FOUND_IN_VERIFIED_CORPUS", method="none")


def verify_parallel_existence(
    connection: sqlite3.Connection,
    provided_name: Optional[str],
    provided_citations: List[str],
) -> ExistenceResult:
    """Resolve a grouped citation, requiring parallel citations to agree."""
    results = [verify_existence(connection, provided_name, citation) for citation in provided_citations]
    resolved = [result for result in results if result.case]
    case_ids = {result.case["case_id"] for result in resolved if result.case}
    if len(case_ids) > 1:
        candidates = [result.case for result in resolved if result.case]
        return ExistenceResult("AMBIGUOUS_MATCH", candidates=candidates, method="parallel_citations_disagree")
    if resolved:
        return resolved[0]
    return results[0] if results else verify_existence(connection, provided_name, None)
