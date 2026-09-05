from __future__ import annotations

from typing import Optional

from urllib.parse import unquote

from backend.app.verifiers.url_classifier import classify_url, normalize_url


def verify_link(href: Optional[str], case: Optional[dict], known_cases: Optional[list[dict]] = None) -> str:
    if not href:
        return "NO_LINK_AVAILABLE"
    known_cases = known_cases or []
    classification = classify_url(href, [item.get("source_url", "") for item in known_cases])
    if classification.status == "MALFORMED_URL":
        return "LINK_BROKEN_OR_INACCESSIBLE"
    haystack = unquote(href).lower()
    if classification.status == "OFFICIAL_SOURCE_SEARCH_PAGE" or any(token in haystack for token in ("/search", "?q=", "?query=", "searchresults")):
        return "LINK_POINTS_TO_SEARCH_RESULTS"
    if not case:
        return "LINK_BROKEN_OR_INACCESSIBLE"
    normalized = classification.normalized_url
    try:
        official = normalize_url(case.get("source_url", "")) if case.get("source_url") else ""
    except ValueError:
        official = ""
    if official and normalized == official:
        return "LINK_CONFIRMS_CASE"
    for known_case in known_cases:
        try:
            known_url = normalize_url(known_case.get("source_url", "")) if known_case.get("source_url") else ""
        except ValueError:
            known_url = ""
        if known_case.get("case_id") != case.get("case_id") and known_url and normalized == known_url:
            return "LINK_RESOLVES_TO_DIFFERENT_CASE"
    identifiers = [case["case_id"].lower(), case.get("neutral_citation", "").replace(" ", "").lower()]
    compact = haystack.replace(" ", "")
    if any(identifier and identifier in compact for identifier in identifiers):
        return "LINK_CONFIRMS_CASE"
    return "LINK_BROKEN_OR_INACCESSIBLE"
