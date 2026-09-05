from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

from backend.app.corpus.search import legal_terms, paragraphs_for_case


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
    sentence_tokens = set(legal_terms(cleaned))
    if not (_CONCLUSION_CUES & sentence_tokens):
        return unable_to_evaluate("The citation sentence does not contain an identifiable legal rule or conclusion to evaluate.")
    evidence = paragraphs_for_case(connection, case_id, cleaned, max_evidence)
    if not evidence:
        return RuleSupportResult("UNSUPPORTED", 0.15, [], "No relevant paragraph was retrieved from the cited judgment; the sentence is not supported by the local evidence index.")
    top = evidence[0]
    paragraph_tokens = set(legal_terms(top["text"]))
    meaningful_overlap = len(sentence_tokens & paragraph_tokens)
    has_support_cue = bool(_SUPPORT_CUES & paragraph_tokens)
    has_rule_context = bool(_CONCLUSION_CUES & sentence_tokens)
    score = float(top["score"])
    if score >= 0.58 and meaningful_overlap >= 3 and has_support_cue and has_rule_context:
        confidence = min(0.92, round(0.48 + score * 0.35 + meaningful_overlap / max(len(sentence_tokens), 1) * 0.10, 2))
        return RuleSupportResult(
            "SUPPORTED",
            confidence,
            evidence,
            f"The top-ranked passage scored {score:.2f} and matched {meaningful_overlap} claim terms while containing operative holding language. This is a retrieval signal, not a legal conclusion.",
            needs_human_review=False,
        )
    if score >= 0.30 and meaningful_overlap >= 2:
        confidence = min(0.7, round(0.18 + score * 0.45 + meaningful_overlap / max(len(sentence_tokens), 1) * 0.08, 2))
        return RuleSupportResult(
            "UNCERTAIN",
            confidence,
            evidence,
            f"The top-ranked passage scored {score:.2f} and matched {meaningful_overlap} claim terms, but the heuristic cannot determine whether it entails the stated legal rule.",
        )
    confidence = min(0.3, round(0.10 + score * 0.25, 2))
    return RuleSupportResult(
        "UNSUPPORTED",
        confidence,
        evidence,
        f"The top-ranked passage scored only {score:.2f} and did not provide enough relevant, operative language to support the stated legal rule.",
    )


def unable_to_evaluate(reason: str) -> RuleSupportResult:
    return RuleSupportResult("UNABLE_TO_EVALUATE", 0.0, [], reason)
