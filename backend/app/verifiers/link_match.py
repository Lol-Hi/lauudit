from __future__ import annotations

from typing import Optional

from urllib.parse import unquote, urlparse


def verify_link(href: Optional[str], case: Optional[dict], known_cases: Optional[list[dict]] = None) -> str:
    if not href:
        return "NO_LINK_AVAILABLE"
    parsed = urlparse(href)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "LINK_BROKEN_OR_INACCESSIBLE"
    haystack = unquote(href).lower()
    if any(token in haystack for token in ("/search", "?q=", "?query=", "searchresults")):
        return "LINK_POINTS_TO_SEARCH_RESULTS"
    if not case:
        return "LINK_BROKEN_OR_INACCESSIBLE"
    official = case.get("source_url", "").rstrip("/").lower()
    if official and href.rstrip("/").lower() == official:
        return "LINK_CONFIRMS_CASE"
    for known_case in known_cases or []:
        known_url = known_case.get("source_url", "").rstrip("/").lower()
        if known_case.get("case_id") != case.get("case_id") and known_url and href.rstrip("/").lower() == known_url:
            return "LINK_RESOLVES_TO_DIFFERENT_CASE"
    identifiers = [case["case_id"].lower(), case.get("neutral_citation", "").replace(" ", "").lower()]
    compact = haystack.replace(" ", "")
    if any(identifier and identifier in compact for identifier in identifiers):
        return "LINK_CONFIRMS_CASE"
    return "LINK_BROKEN_OR_INACCESSIBLE"
