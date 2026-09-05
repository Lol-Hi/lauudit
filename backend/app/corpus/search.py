from __future__ import annotations

import re
import sqlite3
from difflib import SequenceMatcher

from backend.app.normalization.case_names import normalize_case_name
from backend.app.normalization.citations import normalize_citation


_SEARCH_STOPWORDS = {
    "about", "after", "again", "against", "being", "between", "could", "court",
    "case", "does", "from", "have", "into", "more", "other", "over", "such",
    "that", "the", "their", "there", "these", "this", "under", "were", "which",
    "while", "with", "would", "where", "when", "what", "also", "and", "for",
    "was", "has", "been", "are", "but", "notwithstanding",
}
_OPERATIVE_TERMS = {
    "allowed", "dismissed", "entitled", "established", "found", "finds", "liable",
    "must", "requires", "sentenced", "held", "holds",
}


def _case(row: sqlite3.Row) -> dict:
    return dict(row)


def by_citation(connection: sqlite3.Connection, citation: str) -> list[dict]:
    value = normalize_citation(citation)
    rows = connection.execute(
        "SELECT c.* FROM cases c JOIN case_citations x ON x.case_id=c.case_id WHERE x.normalized_citation=?",
        (value,),
    ).fetchall()
    return [_case(row) for row in rows]


def by_exact_name(connection: sqlite3.Connection, name: str) -> list[dict]:
    value = normalize_case_name(name)
    rows = connection.execute(
        "SELECT * FROM cases WHERE normalized_name=? UNION SELECT c.* FROM cases c JOIN case_aliases a ON a.case_id=c.case_id WHERE a.normalized_alias=?",
        (value, value),
    ).fetchall()
    return [_case(row) for row in rows]


def fuzzy_names(connection: sqlite3.Connection, name: str, threshold: float = 0.72) -> list[dict]:
    target = normalize_case_name(name)
    rows = connection.execute("SELECT * FROM cases").fetchall()
    ranked: list[tuple[float, dict]] = []
    for row in rows:
        candidates = [row["normalized_name"]]
        aliases = connection.execute("SELECT normalized_alias FROM case_aliases WHERE case_id=?", (row["case_id"],)).fetchall()
        candidates.extend(item[0] for item in aliases)
        score = max(SequenceMatcher(None, target, candidate).ratio() for candidate in candidates)
        if score >= threshold:
            item = _case(row)
            item["match_score"] = round(score, 4)
            ranked.append((score, item))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in ranked[:5]]


def legal_terms(text: str) -> list[str]:
    """Return stable content terms used by the deterministic evidence ranker."""
    return [
        term
        for term in re.findall(r"[a-zA-Z]{3,}", text.lower())
        if term not in _SEARCH_STOPWORDS
    ]


def paragraphs_for_case(connection: sqlite3.Connection, case_id: str, query: str, limit: int = 3) -> list[dict]:
    if limit <= 0:
        return []
    terms = legal_terms(query)
    query_set = set(terms)
    query_bigrams = set(zip(terms, terms[1:]))
    rows = connection.execute(
        "SELECT paragraph_number, text, page_number, text_source FROM paragraphs WHERE case_id=?",
        (case_id,),
    ).fetchall()
    scored: list[dict] = []
    for row in rows:
        paragraph_terms = legal_terms(row["text"])
        paragraph_set = set(paragraph_terms)
        overlap = query_set & paragraph_set
        if not overlap:
            continue

        coverage = len(overlap) / max(len(query_set), 1)
        precision = len(overlap) / max(len(paragraph_set), 1)
        paragraph_bigrams = set(zip(paragraph_terms, paragraph_terms[1:]))
        phrase_coverage = len(query_bigrams & paragraph_bigrams) / max(len(query_bigrams), 1)
        operative_bonus = 1.0 if _OPERATIVE_TERMS & paragraph_set else 0.0
        # Coverage leads: a paragraph should match the claim's terms. Precision,
        # phrase continuity, and operative language break otherwise close ties.
        score = (
            coverage * 0.65
            + precision * 0.15
            + phrase_coverage * 0.10
            + operative_bonus * 0.10
        )
        scored.append({
            "paragraph": row["paragraph_number"],
            "text": row["text"],
            "score": round(min(score, 1.0), 4),
            "page": row["page_number"],
            "text_source": row["text_source"],
        })
    scored.sort(key=lambda item: (item["score"], len(legal_terms(item["text"])), -item["paragraph"]), reverse=True)
    return scored[:limit]
