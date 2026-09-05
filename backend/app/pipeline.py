from __future__ import annotations

import uuid

from backend.app.config import settings
from backend.app.corpus.database import connect, current_corpus, initialize_schema
from backend.app.extractors.citations import extract_citations
from backend.app.extractors.links import link_for_citation
from backend.app.scoring import citation_status
from backend.app.schemas import AuditRequest, AuditResponse, AuditSummary, CitationAudit, Evidence
from backend.app.verifiers.existence import verify_existence
from backend.app.verifiers.link_match import verify_link
from backend.app.verifiers.name_match import verify_name
from backend.app.verifiers.rule_support import evaluate_rule_support, unable_to_evaluate
from backend.app.verifiers.url_classifier import classify_url


def run_audit(request: AuditRequest) -> AuditResponse:
    connection = connect(settings.absolute_db_path)
    initialize_schema(connection)
    corpus = current_corpus(connection)
    extracted = extract_citations(request.response_text)
    known_cases = [dict(row) for row in connection.execute("SELECT * FROM cases").fetchall()]
    known_source_urls = [item["source_url"] for item in known_cases if item.get("source_url")]
    audits: list[CitationAudit] = []
    for citation in extracted:
        href = link_for_citation(citation, request.links)
        url_result = classify_url(href, known_source_urls)
        existence = verify_existence(connection, citation.provided_name, citation.provided_citation)
        case = existence.case
        name_matches, name_status = verify_name(citation.provided_name, case)
        link_status = verify_link(href, case, known_cases)
        if case and settings.rule_evaluator == "heuristic":
            support = evaluate_rule_support(connection, case["case_id"], citation.surrounding_sentence, settings.max_evidence)
        elif case:
            support = unable_to_evaluate(f"Rule evaluator '{settings.rule_evaluator}' is not enabled in this first iteration.")
        else:
            support = unable_to_evaluate("No unique corpus case was resolved, so rule support cannot be evaluated.")
        status = citation_status(existence.status, name_matches, link_status, support.classification)
        needs_review = status != "VERIFIED_EXISTS" or support.classification != "SUPPORTED"
        audits.append(CitationAudit(
            occurrence_id=citation.occurrence_id,
            raw_text=citation.raw_text,
            provided_name=citation.provided_name,
            provided_citation=citation.provided_citation,
            surrounding_sentence=citation.surrounding_sentence,
            canonical_name=case["canonical_name"] if case else None,
            case_id=case["case_id"] if case else None,
            source_url=case["source_url"] if case else None,
            source_status=url_result.status if href else None,
            source_url_normalized=url_result.normalized_url,
            case_exists=case is not None and existence.status == "VERIFIED_EXISTS",
            existence_status=existence.status,
            name_matches=name_matches,
            name_status=name_status,
            link_status=link_status,
            rule_support=support.classification,
            rule_confidence=support.confidence,
            explanation=existence.status + ". " + url_result.reason + " " + support.explanation,
            evidence=[Evidence(**item) for item in support.evidence],
            candidates=(existence.candidates or [])[:5],
            needs_human_review=needs_review,
            status=status,
        ))
    connection.close()
    summary = AuditSummary(
        total_citations=len(audits),
        verified_cases=sum(item.case_exists for item in audits),
        name_mismatches=sum(item.name_matches is False for item in audits),
        not_found=sum(item.existence_status == "NOT_FOUND_IN_VERIFIED_CORPUS" for item in audits),
        link_errors=sum(item.link_status in {"LINK_RESOLVES_TO_DIFFERENT_CASE", "LINK_BROKEN_OR_INACCESSIBLE", "LINK_POINTS_TO_SEARCH_RESULTS"} for item in audits),
        unsupported_rules=sum(item.rule_support == "UNSUPPORTED" for item in audits),
    )
    overall = "PASS" if audits and all(item.status == "VERIFIED_EXISTS" for item in audits) else ("NO_CITATIONS" if not audits else "REVIEW_REQUIRED")
    return AuditResponse(
        audit_id=f"audit-{uuid.uuid4().hex[:12]}",
        jurisdiction=request.jurisdiction,
        corpus_snapshot=corpus["snapshot_id"] if corpus else "untracked",
        corpus_completeness=corpus["completeness"] if corpus else "unknown",
        corpus_notes=corpus["notes"] if corpus else "The SQLite index has no recorded corpus snapshot.",
        overall_status=overall,
        summary=summary,
        citations=audits,
    )
