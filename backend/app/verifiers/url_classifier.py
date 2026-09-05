"""Offline URL provenance classification.

This module deliberately does not perform network requests. An official-domain
classification is a provenance signal, not confirmation that the URL is live
or that it points to the cited case.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


URL_STATUSES = {
    "KNOWN_CORPUS_SOURCE",
    "OFFICIAL_ELITIGATION_SOURCE",
    "OFFICIAL_JUDICIARY_SOURCE",
    "OFFICIAL_SOURCE_SEARCH_PAGE",
    "UNVERIFIED_EXTERNAL_URL",
    "MALFORMED_URL",
}


@dataclass(frozen=True)
class URLClassification:
    status: str
    normalized_url: Optional[str]
    host: Optional[str]
    reason: str


def normalize_url(raw_url: str) -> str:
    """Normalize URLs for safe, deterministic metadata comparison."""
    value = raw_url.strip()
    parsed = urlsplit(value)
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise ValueError("URL must use HTTP or HTTPS")
    if not parsed.hostname:
        raise ValueError("URL has no hostname")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing credentials are not accepted")

    hostname = parsed.hostname.lower()
    port = parsed.port  # Raises ValueError for malformed ports.
    netloc = hostname
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{hostname}:{port}"

    path = re.sub(r"/+", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
    return urlunsplit((scheme, netloc, path, query, ""))


def _is_domain_or_subdomain(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def classify_url(raw_url: Optional[str], known_source_urls: Optional[Iterable[str]] = None) -> URLClassification:
    if not raw_url or not raw_url.strip():
        return URLClassification("MALFORMED_URL", None, None, "No usable hyperlink URL was provided.")
    try:
        normalized = normalize_url(raw_url)
        parsed = urlsplit(normalized)
        host = parsed.hostname or ""
    except (TypeError, ValueError):
        return URLClassification("MALFORMED_URL", None, None, "The hyperlink is not a valid HTTP or HTTPS URL.")

    known_urls: set[str] = set()
    for source_url in known_source_urls or []:
        try:
            known_urls.add(normalize_url(source_url))
        except (TypeError, ValueError):
            continue
    if normalized in known_urls:
        return URLClassification("KNOWN_CORPUS_SOURCE", normalized, host, "The URL exactly matches a source URL in the local corpus.")

    path = parsed.path.lower().rstrip("/")
    query_keys = {key.lower() for key, _ in parse_qsl(parsed.query)}
    is_search_page = (
        path.endswith("/gdviewer/home/index")
        or path.endswith("/search")
        or bool({"searchphrase", "searchquerytime", "searchtotalhits", "currentpage"} & query_keys)
    )

    if _is_domain_or_subdomain(host, "elitigation.sg"):
        if is_search_page:
            return URLClassification("OFFICIAL_SOURCE_SEARCH_PAGE", normalized, host, "The URL appears to be an eLitigation search or results page.")
        return URLClassification("OFFICIAL_ELITIGATION_SOURCE", normalized, host, "The URL belongs to the official eLitigation domain.")

    if _is_domain_or_subdomain(host, "judiciary.gov.sg"):
        if is_search_page:
            return URLClassification("OFFICIAL_SOURCE_SEARCH_PAGE", normalized, host, "The URL appears to be an official Singapore Courts search page.")
        return URLClassification("OFFICIAL_JUDICIARY_SOURCE", normalized, host, "The URL belongs to the official Singapore Courts domain.")

    return URLClassification("UNVERIFIED_EXTERNAL_URL", normalized, host, "The URL is valid but is not from a configured official source.")

