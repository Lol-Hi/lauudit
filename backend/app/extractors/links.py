from __future__ import annotations

from typing import Optional

from backend.app.schemas import LinkInput


def link_for_citation(citation, links: list[LinkInput]) -> Optional[str]:
    raw = citation.raw_text.lower()
    name = (citation.provided_name or "").lower()
    citation_text = (citation.provided_citation or "").lower()
    ranked: list[tuple[int, str]] = []
    for link in links:
        anchor = link.text.lower()
        context = link.context.lower()
        score = 0
        if raw and raw in anchor:
            score = 100
        elif name and name in anchor and (not citation_text or citation_text in anchor):
            score = 90
        elif name and name in anchor:
            score = 80
        elif raw and raw in context:
            score = 50
        elif name and name in context:
            score = 40
        if score:
            ranked.append((score, link.href))
    return max(ranked, key=lambda item: item[0])[1] if ranked else None
