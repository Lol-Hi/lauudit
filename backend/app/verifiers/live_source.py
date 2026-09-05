"""Explicit, read-only verification of approved online legal sources.

This module is deliberately isolated from the audit pipeline. It is intended
to be called only by a future explicit online-verification endpoint or a
manual maintenance command; importing the deterministic audit path must never
cause a network request.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Callable, Optional
from urllib.parse import urljoin, urlsplit

import httpx

from backend.app.extractors.citations import NEUTRAL_CITATION_RE
from backend.app.normalization.case_names import name_matches_canonical
from backend.app.normalization.citations import normalize_citation
from backend.app.verifiers.url_classifier import classify_url, normalize_url


LIVE_ALLOWED_HOSTS = {
    "elitigation.sg",
    "www.elitigation.sg",
    "judiciary.gov.sg",
    "www.judiciary.gov.sg",
    "singaporelawwatch.sg",
    "www.singaporelawwatch.sg",
}
TRUSTED_FOR_LIVE_FETCH = {
    "OFFICIAL_ELITIGATION_SOURCE",
    "OFFICIAL_JUDICIARY_SOURCE",
    "TRUSTED_PUBLISHER_SOURCE",
}
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_REDIRECTS = 5
REDIRECT_STATUSES = {301, 302, 303, 307, 308}
DATE_RE = re.compile(
    r"\b(?P<day>\d{1,2})\s+(?P<month>January|February|March|April|May|June|July|August|September|October|November|December)\s+(?P<year>\d{4})\b",
    re.I,
)
MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


@dataclass(frozen=True)
class LiveVerificationResult:
    status: str
    attempted: bool
    source_verified: bool
    final_url: Optional[str] = None
    retrieved_at: Optional[str] = None
    metadata_match: dict[str, Optional[bool]] = field(default_factory=dict)
    case_name: Optional[str] = None
    neutral_citation: Optional[str] = None
    court_code: Optional[str] = None
    decision_date: Optional[str] = None
    reason: str = ""


class _ClassTextParser(HTMLParser):
    """Collect text from the metadata classes used by public judgment pages."""

    TARGET_CLASSES = {"HN-CaseName", "HN-NeutralCit", "Judg-Date-Reserved", "CaseNumber"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._captures: dict[str, list[list[str]]] = {}
        self._active: list[tuple[str, int, list[str]]] = []
        self._depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        self._depth += 1
        classes = set((dict(attrs).get("class") or "").split())
        for target in self.TARGET_CLASSES & classes:
            buffer: list[str] = []
            self._captures.setdefault(target, []).append(buffer)
            self._active.append((target, self._depth, buffer))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        for _, _, buffer in self._active:
            buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self._active) - 1, -1, -1):
            _, start_depth, _ = self._active[index]
            if start_depth == self._depth:
                self._active.pop(index)
                break
        self._depth = max(0, self._depth - 1)

    def values(self, target: str) -> list[str]:
        return [
            " ".join("".join(value).split())
            for value in self._captures.get(target, [])
            if "".join(value).strip()
        ]


def _allowlisted_host(url: str) -> bool:
    return (urlsplit(url).hostname or "").lower() in LIVE_ALLOWED_HOSTS


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_metadata(html: str) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
    parser = _ClassTextParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        return None, None, None, None, None

    citation_values = parser.values("HN-NeutralCit")
    citation = next((value for value in citation_values if NEUTRAL_CITATION_RE.search(value)), None)
    if not citation:
        match = NEUTRAL_CITATION_RE.search(html)
        citation = match.group(0) if match else None
    citation_match = NEUTRAL_CITATION_RE.search(citation or "")
    court_code = citation_match.group("code").upper() if citation_match else None

    names = [value for value in parser.values("HN-CaseName") if not NEUTRAL_CITATION_RE.search(value)]
    case_name = names[0] if names else None

    date_value = next(iter(parser.values("Judg-Date-Reserved")), None)
    decision_date = None
    if date_value:
        date_match = DATE_RE.search(date_value)
        if date_match:
            decision_date = (
                f"{date_match.group('year')}-{MONTHS[date_match.group('month').lower()]:02d}-"
                f"{int(date_match.group('day')):02d}"
            )

    court_text = next(iter(parser.values("CaseNumber")), None)
    return case_name, citation, court_code, decision_date, court_text


def _client_fetcher(**client_kwargs: object) -> httpx.Client:
    return httpx.Client(**client_kwargs)


def verify_live_source(
    source_url: str,
    expected: dict,
    *,
    timeout: float = 10.0,
    client_factory: Callable[..., httpx.Client] = _client_fetcher,
) -> LiveVerificationResult:
    """Verify one approved source without retaining its document.

    The expected mapping normally contains ``canonical_name``, and may also
    contain ``neutral_citation``, ``court`` or ``court_code``, and
    ``decision_date``. ``client_factory`` is injectable for tests.
    """
    try:
        normalized_url = normalize_url(source_url)
    except (TypeError, ValueError):
        return LiveVerificationResult(
            "LIVE_VERIFICATION_SKIPPED_UNTRUSTED_HOST",
            attempted=False,
            source_verified=False,
            reason="The source URL is not a valid public HTTP(S) URL.",
        )

    if not _allowlisted_host(normalized_url):
        return LiveVerificationResult(
            "LIVE_VERIFICATION_SKIPPED_UNTRUSTED_HOST",
            attempted=False,
            source_verified=False,
            reason="The source host is not on the live-verification allowlist.",
        )

    classification = classify_url(normalized_url)
    if classification.status not in TRUSTED_FOR_LIVE_FETCH:
        return LiveVerificationResult(
            "LIVE_VERIFICATION_SKIPPED_UNTRUSTED_HOST",
            attempted=False,
            source_verified=False,
            reason="The source is not a direct trusted document page; search pages are not fetched.",
        )

    retrieved_at = _now_iso()
    current_url = normalized_url
    try:
        with client_factory(
            follow_redirects=False,
            timeout=timeout,
            headers={"User-Agent": "Lauudit-Verifier/0.1 (read-only hackathon prototype)"},
        ) as client:
            for _ in range(MAX_REDIRECTS + 1):
                response = client.get(current_url)
                if response.status_code not in REDIRECT_STATUSES:
                    break
                location = response.headers.get("location")
                if not location:
                    break
                try:
                    redirect_url = normalize_url(urljoin(current_url, location))
                except (TypeError, ValueError):
                    return LiveVerificationResult(
                        "LIVE_SOURCE_UNAVAILABLE",
                        attempted=True,
                        source_verified=False,
                        final_url=location,
                        retrieved_at=retrieved_at,
                        reason="The source redirect target is invalid.",
                    )
                if not _allowlisted_host(redirect_url):
                    return LiveVerificationResult(
                        "LIVE_SOURCE_UNAVAILABLE",
                        attempted=True,
                        source_verified=False,
                        final_url=redirect_url,
                        retrieved_at=retrieved_at,
                        reason="The source redirected outside the live-verification allowlist.",
                    )
                redirect_classification = classify_url(redirect_url)
                if redirect_classification.status not in TRUSTED_FOR_LIVE_FETCH:
                    return LiveVerificationResult(
                        "LIVE_SOURCE_UNAVAILABLE",
                        attempted=True,
                        source_verified=False,
                        final_url=redirect_url,
                        retrieved_at=retrieved_at,
                        reason="The source redirected to a search or non-document page.",
                    )
                current_url = redirect_url
            else:
                return LiveVerificationResult(
                    "LIVE_SOURCE_UNAVAILABLE",
                    attempted=True,
                    source_verified=False,
                    final_url=current_url,
                    retrieved_at=retrieved_at,
                    reason="The source exceeded the configured redirect limit.",
                )
    except httpx.HTTPError as exc:
        return LiveVerificationResult(
            "LIVE_SOURCE_UNAVAILABLE",
            attempted=True,
            source_verified=False,
            final_url=current_url,
            retrieved_at=retrieved_at,
            reason=f"Live fetch failed: {exc}",
        )

    final_url_normalized = current_url
    if not response.is_success:
        return LiveVerificationResult(
            "LIVE_SOURCE_UNAVAILABLE",
            attempted=True,
            source_verified=False,
            final_url=final_url_normalized,
            retrieved_at=retrieved_at,
            reason=f"The source returned HTTP {response.status_code}.",
        )

    content_type = response.headers.get("content-type", "").lower()
    if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
        return LiveVerificationResult(
            "LIVE_UNSUPPORTED_FORMAT",
            attempted=True,
            source_verified=False,
            final_url=final_url_normalized,
            retrieved_at=retrieved_at,
            reason="The source is not an HTML judgment page; PDF extraction is a later increment.",
        )

    body = response.content
    if len(body) > MAX_RESPONSE_BYTES:
        return LiveVerificationResult(
            "LIVE_UNSUPPORTED_FORMAT",
            attempted=True,
            source_verified=False,
            final_url=final_url_normalized,
            retrieved_at=retrieved_at,
            reason="The source response exceeded the configured safety limit.",
        )

    case_name, neutral_citation, court_code, decision_date, court_text = _parse_metadata(response.text)
    if not case_name and not neutral_citation:
        return LiveVerificationResult(
            "LIVE_SOURCE_NOT_A_JUDGMENT",
            attempted=True,
            source_verified=False,
            final_url=final_url_normalized,
            retrieved_at=retrieved_at,
            reason="The page did not expose recognizable judgment metadata.",
        )

    metadata_match: dict[str, Optional[bool]] = {}
    expected_name = expected.get("canonical_name") or expected.get("name")
    expected_citation = expected.get("neutral_citation")
    expected_court_code = expected.get("court_code")
    expected_court = expected.get("court")
    expected_date = expected.get("decision_date")

    if expected_name:
        metadata_match["name"] = name_matches_canonical(expected_name, case_name)
    if expected_citation:
        metadata_match["citation"] = bool(neutral_citation) and normalize_citation(expected_citation) == normalize_citation(neutral_citation)
    if expected_court_code:
        metadata_match["court_code"] = bool(court_code) and expected_court_code.upper() == court_code.upper()
    if expected_court:
        metadata_match["court"] = bool(court_text) and expected_court.lower() in court_text.lower()
    if expected_date:
        metadata_match["date"] = expected_date == decision_date

    if not metadata_match:
        return LiveVerificationResult(
            "LIVE_SOURCE_NOT_A_JUDGMENT",
            attempted=True,
            source_verified=False,
            final_url=final_url_normalized,
            retrieved_at=retrieved_at,
            case_name=case_name,
            neutral_citation=neutral_citation,
            court_code=court_code,
            decision_date=decision_date,
            reason="No expected metadata was supplied for comparison.",
        )

    source_verified = all(value is True for value in metadata_match.values())
    return LiveVerificationResult(
        "LIVE_VERIFIED" if source_verified else "LIVE_METADATA_MISMATCH",
        attempted=True,
        source_verified=source_verified,
        final_url=final_url_normalized,
        retrieved_at=retrieved_at,
        metadata_match=metadata_match,
        case_name=case_name,
        neutral_citation=neutral_citation,
        court_code=court_code,
        decision_date=decision_date,
        reason=(
            "Live metadata comparison completed."
            if source_verified
            else "One or more expected metadata fields did not match the source."
        ),
    )
