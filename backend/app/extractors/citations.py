from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, Tuple


NEUTRAL_CITATION_RE = re.compile(
    r"\[(?P<year>19\d{2}|20\d{2})\]\s*(?P<code>SGCA\(A\)|SGCA|SGHC\(A\)|SGHC|SGDC|SGMC)\s*(?P<number>\d+)",
    re.I,
)
REPORTED_CITATION_RE = re.compile(
    r"\[(?P<year>19\d{2}|20\d{2})\]\s*(?P<volume>\d+)\s+SLR\s+(?P<number>\d+)",
    re.I,
)
PARTY_WORD = r"(?:[A-Z(][A-Za-z0-9'’().&/-]*|&|and|another|others|ors|of|the|appeal|matter|formerly|known|as)"
CASE_NAME_RE = re.compile(
    rf"\b(?P<left>(?:Public Prosecutor|PP|Attorney-General|{PARTY_WORD}(?:\s+{PARTY_WORD}){{0,17}}))\s+"
    r"(?P<separator>(?i:v\.?|versus|&))\s+"
    rf"(?P<right>(?:Public Prosecutor|PP|{PARTY_WORD}(?:\s+{PARTY_WORD}){{0,17}}))",
)
FOOTNOTE_MARKER_RE = re.compile(r"^\s*(?:\[\^(?P<bracket>\d+)\]|\^(?P<caret>\d+)|(?P<plain>\d+)[.)])\s+")
REFERENCE_GAP_RE = re.compile(r"^[\s\u2022•·●\-–—]*(?:\d+[.)]?[\s\u2022•·●\-–—]*)*$")


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
    parallel_citations: list[str] = field(default_factory=list)
    context_type: str = "body"
    footnote_number: Optional[str] = None


def _sentence(text: str, start: int, end: int) -> str:
    left = max(
        text.rfind(".", 0, start),
        text.rfind("!", 0, start),
        text.rfind("?", 0, start),
        text.rfind("\n", 0, start),
    )
    right_candidates = [
        x for x in (text.find(".", end), text.find("!", end), text.find("?", end), text.find("\n", end))
        if x >= 0
    ]
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


def _footnote_metadata(text: str, start: int) -> Tuple[str, Optional[str]]:
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    line = text[line_start:] if line_end < 0 else text[line_start:line_end]
    marker = FOOTNOTE_MARKER_RE.match(line)
    if not marker:
        return "body", None
    number = marker.group("bracket") or marker.group("caret") or marker.group("plain")
    return "footnote", number


def _make_occurrence(text: str, matches: list[re.Match[str]], index: int) -> ExtractedCitation:
    first_match = matches[0]
    last_match = matches[-1]
    sentence = _sentence(text, first_match.start(), last_match.end())
    citations = [match.group(0) for match in matches]
    first_citation = citations[0]
    name, _, _ = _best_name(sentence, sentence.find(first_citation))
    context_type, footnote_number = _footnote_metadata(text, first_match.start())
    citation_text = text[first_match.start() : last_match.end()]
    return ExtractedCitation(
        occurrence_id=f"citation-{index:03d}",
        raw_text=(f"{name} {citation_text}" if name and sentence.find(name) <= sentence.find(first_citation) else citation_text),
        provided_name=name,
        provided_citation=first_citation,
        surrounding_sentence=sentence,
        start=first_match.start(),
        end=last_match.end(),
        parallel_citations=citations if len(citations) > 1 else [],
        context_type=context_type,
        footnote_number=footnote_number,
    )


def _is_parallel_gap(value: str) -> bool:
    # A line break normally separates reference-list entries, not parallel
    # citations. Keep grouping for inline punctuation/conjunctions only.
    return bool(re.fullmatch(r"[ \t]*(?:[,;]|and)[ \t]*", value, flags=re.I))


def _group_parallel_matches(text: str, matches: list[re.Match[str]]) -> list[list[re.Match[str]]]:
    groups: list[list[re.Match[str]]] = []
    for match in matches:
        if groups:
            previous = groups[-1][-1]
            gap = text[previous.end() : match.start()]
            if _same_sentence(text, previous.end(), match.start()) and _is_parallel_gap(gap):
                groups[-1].append(match)
                continue
        groups.append([match])
    return groups


def _same_sentence(text: str, first_end: int, second_start: int) -> bool:
    return not re.search(r"[.!?]", text[first_end:second_start])


def _pair_wrapped_reference_lines(text: str, results: list[ExtractedCitation]) -> list[ExtractedCitation]:
    """Pair a case name with its citation when a rendered reference wraps lines.

    Legal-AI reference lists commonly render the case name, a footnote marker,
    and the neutral citation as separate DOM lines. The ordinary sentence
    extractor intentionally treats newlines as boundaries, so pair only the
    narrow, unambiguous pattern of a name-only occurrence immediately followed
    by a citation-only occurrence with whitespace/bullet/number material in the
    gap. Ordinary adjacent references remain separate.
    """
    paired: list[ExtractedCitation] = []
    index = 0
    while index < len(results):
        current = results[index]
        if index + 1 < len(results):
            following = results[index + 1]
            gap = text[current.end : following.start]
            can_pair = (
                current.provided_name
                and current.provided_citation is None
                and following.provided_name is None
                and following.provided_citation is not None
                and len(gap) <= 96
                and REFERENCE_GAP_RE.fullmatch(gap) is not None
                and current.context_type == following.context_type
            )
            if can_pair:
                current.provided_citation = following.provided_citation
                current.parallel_citations = following.parallel_citations
                current.raw_text = text[current.start : following.end].strip()
                current.surrounding_sentence = text[current.start : following.end].strip()
                current.end = following.end
                paired.append(current)
                index += 2
                continue
        paired.append(current)
        index += 1
    return paired


def extract_citations(text: str) -> list[ExtractedCitation]:
    matches = list(NEUTRAL_CITATION_RE.finditer(text)) + list(REPORTED_CITATION_RE.finditer(text))
    matches.sort(key=lambda m: m.start())
    groups = _group_parallel_matches(text, matches)
    results = [_make_occurrence(text, group, i + 1) for i, group in enumerate(groups)]
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
                context_type=_footnote_metadata(text, match.start())[0],
                footnote_number=_footnote_metadata(text, match.start())[1],
            )
        )
        next_index += 1
    results.sort(key=lambda item: item.start)
    results = _pair_wrapped_reference_lines(text, results)
    for i, item in enumerate(results, 1):
        item.occurrence_id = f"citation-{i:03d}"
    return results
