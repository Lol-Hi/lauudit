from __future__ import annotations

from typing import Optional, Tuple

from backend.app.normalization.case_names import name_matches_canonical


def verify_name(provided_name: Optional[str], case: Optional[dict]) -> Tuple[Optional[bool], Optional[str]]:
    if not case:
        return None, None
    matches = name_matches_canonical(provided_name, case["canonical_name"])
    if matches is True:
        return True, "CANONICAL_NAME_MATCH"
    if matches is False:
        return False, "VERIFIED_EXISTS_NAME_MISMATCH"
    return None, "NAME_NOT_PROVIDED"
