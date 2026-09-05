from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from backend.app.schemas import LinkInput


@dataclass(frozen=True)
class LinkResolution:
    href: Optional[str]
    hrefs: tuple[str, ...]
    status: str  # NONE, SINGLE, AMBIGUOUS


def _normalise(value: str) -> str:
    return " ".join(value.casefold().split())


def _compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _normalise(value))


def _same_context(first: LinkInput, second: LinkInput) -> bool:
    first_context = _compact(first.context)
    second_context = _compact(second.context)
    return bool(first_context and first_context == second_context)


def _unique_resolution(hrefs: list[str]) -> LinkResolution:
    unique_hrefs = tuple(dict.fromkeys(hrefs))
    if not unique_hrefs:
        return LinkResolution(None, (), "NONE")
    if len(unique_hrefs) == 1:
        return LinkResolution(unique_hrefs[0], unique_hrefs, "SINGLE")
    return LinkResolution(None, unique_hrefs, "AMBIGUOUS")


def resolve_links(citation, links: list[LinkInput]) -> LinkResolution:
    """Resolve links using positional metadata, then text/context fallbacks.

    Browser-provided offsets are the strongest signal because they preserve the
    exact relationship between a citation occurrence and its source anchor.
    Older clients may omit them, so the existing text/context heuristics remain
    as a compatibility fallback. Different URLs are returned as ambiguous
    instead of being guessed.
    """
    positional = [
        link.href
        for link in links
        if link.start is not None
        and link.end is not None
        and link.start < citation.end
        and link.end > citation.start
    ]
    if positional:
        return _unique_resolution(positional)

    raw = _compact(citation.raw_text)
    name = _compact(citation.provided_name or "")
    citation_text = _compact(citation.provided_citation or "")

    # Detect a citation split across adjacent anchors before considering a
    # partial name anchor on its own.
    for index in range(len(links) - 1):
        first, second = links[index], links[index + 1]
        combined = _compact(first.text + second.text)
        if raw and raw in combined and (_same_context(first, second) or not first.context or not second.context):
            return _unique_resolution([first.href, second.href])

    exact: list[str] = []
    for link in links:
        anchor = _compact(link.text)
        if raw and raw in anchor:
            exact.append(link.href)
        elif name and name in anchor and (not citation_text or citation_text in anchor):
            exact.append(link.href)
        elif not citation_text and name and name in anchor:
            exact.append(link.href)
    if exact:
        return _unique_resolution(exact)

    # Context matching is a fallback. It is accepted only when exactly one
    # URL is implicated, avoiding arbitrary selection in dense paragraphs.
    context_matches = [
        link.href
        for link in links
        if (raw and raw in _compact(link.context)) or (name and name in _compact(link.context))
    ]
    if context_matches and len(set(context_matches)) == 1:
        return _unique_resolution(context_matches)
    if context_matches:
        return _unique_resolution(context_matches)
    return LinkResolution(None, (), "NONE")


def link_for_citation(citation, links: list[LinkInput]) -> Optional[str]:
    """Backward-compatible wrapper returning only an unambiguous URL."""
    return resolve_links(citation, links).href
