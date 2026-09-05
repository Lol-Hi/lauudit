from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple


NEUTRAL_CITATION_RE = re.compile(
    r"\[(?P<year>19\d{2}|20\d{2})\]\s*(?P<code>SGCA\(A\)|SGCA|SGHC\(A\)|SGHC|SGDC|SGMC)\s*(?P<number>\d+)",
    re.I,
)
REPORTED_CITATION_RE = re.compile(
    r"\[(?P<year>19\d{2}|20\d{2})\]\s*(?P<volume>\d+)\s+SLR\s+(?P<number>\d+)",
    re.I,
)
CASE_NAME_RE = re.compile(
    r"\b(?P<left>(?:Public Prosecutor|PP|Attorney-General|[A-Z][A-Za-z'’_-]+(?:\s+[A-Z][A-Za-z'’_-]+){0,5}))\s+"
    r"(?P<separator>v\.?|versus|&)\s+"
    r"(?P<right>(?:Public Prosecutor|PP|[A-Z][A-Za-z'’_-]+(?:\s+[A-Z][A-Za-z'’_-]+){0,6}))",
    re.I,
)


@dataclass
class ExtractedCitation:
    occurrence_id: str
    raw_text: str
    provided_name: Optional[str]
    provided_citation: Optional[str]
    surrounding_sentence: str
    start: int
    end: int
    href: Optional[str] = None


def _sentence(text: str, start: int, end: int) -> str:
    left = max(text.rfind(".", 0, start), text.rfind("!", 0, start), text.rfind("?", 0, start))
    right_candidates = [x for x in (text.find(".", end), text.find("!", end), text.find("?", end)) if x >= 0]
    right = min(right_candidates) if right_candidates else len(text)
    return text[left + 1 : right + 1].strip()


def _clean_case_name(value: str) -> str:
    value = value.strip(" \t,;:()[]")
    value = re.sub(r"^(?:the\s+)?(?:response|answer|text|analysis)\s+(?:cites?|mentions?|discusses?|refers?\s+to)\s+", "", value, flags=re.I)
    value = re.sub(r"^(?:the\s+)?(?:court|judge|decision|case)\s+(?:in|of|at)\s+", "", value, flags=re.I)
    value = re.split(r"\s+(?:was|is|has|held|holds|said|stated|noted|decided|also|without|where)\b", value, maxsplit=1, flags=re.I)[0]
    return re.sub(r"\s+", " ", value).strip(" \t,;:()[]")


def _best_name(sentence: str, citation_offset: Optional[int] = None) -> Tuple[Optional[str], Optional[int], Optional[int]]:
    matches = list(CASE_NAME_RE.finditer(sentence))
    if not matches:
        return None, None, None
    if citation_offset is None:
        match = matches[0]
    else:
        match = min(matches, key=lambda item: abs(item.start() - citation_offset))
    raw = _clean_case_name(match.group(0))
    return raw, match.start(), match.end()


def _make_occurrence(text: str, match: re.Match[str], index: int) -> ExtractedCitation:
    sentence = _sentence(text, match.start(), match.end())
    citation = match.group(0)
    name, _, _ = _best_name(sentence, sentence.find(citation))
    return ExtractedCitation(
        occurrence_id=f"citation-{index:03d}",
        raw_text=(f"{name} {citation}" if name and sentence.find(name) <= sentence.find(citation) else citation),
        provided_name=name,
        provided_citation=citation,
        surrounding_sentence=sentence,
        start=match.start(),
        end=match.end(),
    )


def extract_citations(text: str) -> list[ExtractedCitation]:
    matches = list(NEUTRAL_CITATION_RE.finditer(text)) + list(REPORTED_CITATION_RE.finditer(text))
    matches.sort(key=lambda m: m.start())
    results = [_make_occurrence(text, match, i + 1) for i, match in enumerate(matches)]
    covered_spans = [(item.start, item.end) for item in results]

    # Name-only citations are included when they are not part of a citation occurrence.
    next_index = len(results) + 1
    for match in CASE_NAME_RE.finditer(text):
        if any(start <= match.start() <= end or start <= match.end() <= end for start, end in covered_spans):
            continue
        sentence = _sentence(text, match.start(), match.end())
        if NEUTRAL_CITATION_RE.search(sentence) or REPORTED_CITATION_RE.search(sentence):
            continue
        results.append(
            ExtractedCitation(
                occurrence_id=f"citation-{next_index:03d}",
                raw_text=_clean_case_name(match.group(0)),
                provided_name=_clean_case_name(match.group(0)),
                provided_citation=None,
                surrounding_sentence=sentence,
                start=match.start(),
                end=match.end(),
            )
        )
        next_index += 1
    results.sort(key=lambda item: item.start)
    for i, item in enumerate(results, 1):
        item.occurrence_id = f"citation-{i:03d}"
    return results
