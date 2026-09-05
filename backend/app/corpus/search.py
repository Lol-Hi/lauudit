from __future__ import annotations

import re
import sqlite3
from difflib import SequenceMatcher

from backend.app.normalization.case_names import normalize_case_name
from backend.app.normalization.citations import normalize_citation


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


def paragraphs_for_case(connection: sqlite3.Connection, case_id: str, query: str, limit: int = 3) -> list[dict]:
    terms = [term for term in re.findall(r"[a-zA-Z]{3,}", query.lower()) if term not in {
        "the", "and", "that", "this", "with", "from", "court", "case", "held", "holding", "under", "where", "was", "were", "has", "have", "for", "into"
    }]
    rows = connection.execute("SELECT paragraph_number, text FROM paragraphs WHERE case_id=?", (case_id,)).fetchall()
    scored = []
    for row in rows:
        tokens = set(re.findall(r"[a-zA-Z]{3,}", row["text"].lower()))
        overlap = len(set(terms) & tokens)
        score = overlap / max(len(set(terms)), 1)
        if overlap:
            scored.append({"paragraph": row["paragraph_number"], "text": row["text"], "score": round(score, 4)})
    scored.sort(key=lambda item: (item["score"], len(item["text"])), reverse=True)
    return scored[:limit]

