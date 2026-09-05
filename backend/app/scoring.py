from __future__ import annotations

from typing import Optional


def citation_status(
    existence_status: str,
    name_matches: Optional[bool],
    link_status: str,
    rule_support: str,
    live_verified: bool = False,
) -> str:
    if live_verified:
        return "LIVE_VERIFIED"
    if existence_status == "NOT_FOUND_IN_VERIFIED_CORPUS":
        return existence_status
    if existence_status in {"AMBIGUOUS_MATCH", "SOURCE_UNAVAILABLE"}:
        return existence_status
    if name_matches is False:
        return "VERIFIED_EXISTS_NAME_MISMATCH"
    if link_status in {"LINK_RESOLVES_TO_DIFFERENT_CASE", "LINK_BROKEN_OR_INACCESSIBLE", "LINK_POINTS_TO_SEARCH_RESULTS", "LINK_SPLIT_OR_AMBIGUOUS"}:
        return "VERIFIED_EXISTS_LINK_MISMATCH"
    if rule_support == "UNSUPPORTED":
        return "VERIFIED_EXISTS_RULE_UNSUPPORTED"
    if rule_support in {"UNCERTAIN", "UNABLE_TO_EVALUATE"}:
        return "VERIFIED_EXISTS_RULE_UNCERTAIN"
    return "VERIFIED_EXISTS"
