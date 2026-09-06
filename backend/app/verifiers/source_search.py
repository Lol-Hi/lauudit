"""Read-only discovery of direct judgment URLs on approved sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Callable, Optional
from urllib.parse import urljoin

import httpx


SEARCH_URL = "https://www.elitigation.sg/gdviewer/Home/Index"
MAX_SEARCH_RESPONSE_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class SearchCandidate:
    url: str
    case_name: Optional[str] = None
    neutral_citation: Optional[str] = None
    decision_date: Optional[str] = None


@dataclass(frozen=True)
class SearchResult:
    attempted: bool
    query: str = ""
    candidates: list[SearchCandidate] = field(default_factory=list)
    request_failed: bool = False


class _ElitigationSearchParser(HTMLParser):
    """Extract only result-card metadata, never judgment body text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.card_depth: Optional[int] = None
        self.card: Optional[dict[str, str]] = None
        self.active_field: Optional[str] = None
        self.active_buffer: list[str] = []
        self.results: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        attributes = {key.lower(): value or "" for key, value in attrs}
        classes = set(attributes.get("class", "").split())
        next_depth = self.depth + (0 if tag.lower() in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"} else 1)
        if tag.lower() == "div" and "gd-card-body" in classes and self.card is None:
            self.card_depth = next_depth
            self.card = {}
        if self.card is not None and tag.lower() == "a":
            if "gd-heardertext" in classes:
                self.active_field = "case_name"
                self.active_buffer = []
                self.card["url"] = attributes.get("href", "")
            elif "citation-num-link" in classes:
                self.active_field = "neutral_citation"
                self.active_buffer = []
            elif "decision-date-link" in classes:
                self.active_field = "decision_date"
                self.active_buffer = []
        self.depth = next_depth

    def handle_data(self, data: str) -> None:
        if self.active_field is not None:
            self.active_buffer.append(data)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        # Void elements such as <br /> do not change the nesting depth.
        void_tags = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
        self.handle_starttag(tag, attrs)
        if tag.lower() not in void_tags:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self.active_field is not None:
            value = " ".join("".join(self.active_buffer).split())
            if value and self.card is not None:
                self.card[self.active_field] = value
            self.active_field = None
            self.active_buffer = []
        if self.card is not None and tag.lower() == "div" and self.depth == self.card_depth:
            if self.card.get("url"):
                self.results.append(self.card)
            self.card = None
            self.card_depth = None
        self.depth = max(0, self.depth - 1)


def _search_query(canonical_name: Optional[str], neutral_citation: Optional[str]) -> str:
    if neutral_citation:
        return f'"{neutral_citation}"'
    return f'"{canonical_name}"' if canonical_name else ""


def search_elitigation(
    canonical_name: Optional[str],
    neutral_citation: Optional[str],
    *,
    client_factory: Callable[..., httpx.Client] = httpx.Client,
) -> SearchResult:
    """Find direct eLitigation judgment URLs for one extracted citation.

    The search URL is fixed to the official Singapore Courts judgments site;
    callers must still run every candidate through ``verify_live_source``.
    """
    query = _search_query(canonical_name, neutral_citation)
    if not query:
        return SearchResult(attempted=False)

    year = ""
    if neutral_citation and neutral_citation.startswith("["):
        year = neutral_citation[1:5]
    params = {
        "Filter": "SUPCT",
        "SearchPhrase": query,
        "YearOfDecision": year or "All",
        "CurrentPage": "1",
        "SortBy": "DateOfDecision",
        "SortAscending": "False",
        "PageSize": "0",
        "Verbose": "False",
        "SearchMode": "True",
    }
    try:
        with client_factory(
            follow_redirects=True,
            timeout=3.0,
            headers={"User-Agent": "Lauudit-Verifier/0.1 (read-only citation search)"},
        ) as client:
            response = client.get(SEARCH_URL, params=params)
    except httpx.HTTPError:
        return SearchResult(attempted=True, query=query, request_failed=True)

    if not response.is_success or len(response.content) > MAX_SEARCH_RESPONSE_BYTES:
        return SearchResult(attempted=True, query=query)
    content_type = response.headers.get("content-type", "").lower()
    if "html" not in content_type:
        return SearchResult(attempted=True, query=query)

    parser = _ElitigationSearchParser()
    try:
        parser.feed(response.text)
        parser.close()
    except Exception:
        return SearchResult(attempted=True, query=query)

    candidates = []
    for item in parser.results:
        href = item.get("url", "")
        if not href.startswith("/gdviewer/s/"):
            continue
        candidates.append(SearchCandidate(
            url=urljoin(SEARCH_URL, href),
            case_name=item.get("case_name"),
            neutral_citation=item.get("neutral_citation"),
            decision_date=item.get("decision_date"),
        ))
    return SearchResult(attempted=True, query=query, candidates=candidates)
