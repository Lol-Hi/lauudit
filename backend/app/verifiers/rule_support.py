from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

from backend.app.corpus.search import paragraphs_for_case


@dataclass
class RuleSupportResult:
    classification: str
    confidence: float
    evidence: list[dict]
    explanation: str
    needs_human_review: bool = True


_SUPPORT_CUES = {"held", "holds", "found", "finds", "requires", "must", "entitled", "liable", "allowed", "dismissed", "established"}
_CONCLUSION_CUES = {"therefore", "accordingly", "conclusion", "rule", "principle", "duty", "breach", "negligence", "contract", "agreement", "sentence", "damages"}


def evaluate_rule_support(connection: sqlite3.Connection, case_id: str, sentence: str, max_evidence: int = 3) -> RuleSupportResult:
    cleaned = re.sub(r"\[[^\]]+\]", " ", sentence)
    sentence_tokens = set(re.findall(r"[a-zA-Z]{4,}", cleaned.lower()))
    if not (_CONCLUSION_CUES & sentence_tokens):
        return unable_to_evaluate("The citation sentence does not contain an identifiable legal rule or conclusion to evaluate.")
    evidence = paragraphs_for_case(connection, case_id, cleaned, max_evidence)
    if not evidence:
        return RuleSupportResult("UNSUPPORTED", 0.15, [], "No relevant paragraph was retrieved from the cited judgment; the sentence is not supported by the local evidence index.")
    top = evidence[0]
    paragraph_tokens = set(re.findall(r"[a-zA-Z]{4,}", top["text"].lower()))
    meaningful_overlap = len(sentence_tokens & paragraph_tokens)
    has_support_cue = bool(_SUPPORT_CUES & paragraph_tokens)
    has_rule_context = bool(_CONCLUSION_CUES & sentence_tokens)
    score = float(top["score"])
    if score >= 0.42 and meaningful_overlap >= 3 and has_support_cue and has_rule_context:
        return RuleSupportResult("SUPPORTED", min(0.9, round(0.5 + score * 0.4, 2)), evidence, "A high-overlap judgment passage contains operative holding language relevant to the cited sentence. This is a retrieval signal, not a legal conclusion.")
    if score >= 0.16 and meaningful_overlap >= 2:
        return RuleSupportResult("UNCERTAIN", min(0.7, round(0.25 + score * 0.4, 2)), evidence, "Some potentially relevant passages were retrieved, but the heuristic cannot determine whether they entail the stated legal rule.")
    return RuleSupportResult("UNSUPPORTED", 0.2, evidence, "The retrieved passages do not provide enough relevant, operative language to support the stated legal rule.")


def unable_to_evaluate(reason: str) -> RuleSupportResult:
    return RuleSupportResult("UNABLE_TO_EVALUATE", 0.0, [], reason)
