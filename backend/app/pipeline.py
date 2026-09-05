from __future__ import annotations

import uuid

from backend.app.config import settings
from backend.app.corpus.database import connect, current_corpus, initialize_schema
from backend.app.extractors.citations import extract_citations
from backend.app.extractors.links import resolve_links
from backend.app.scoring import citation_status
from backend.app.schemas import AuditRequest, AuditResponse, AuditSummary, CitationAudit, Evidence, LiveVerifyResponse
from backend.app.verifiers.existence import verify_existence, verify_parallel_existence
from backend.app.verifiers.link_match import verify_link
from backend.app.verifiers.name_match import verify_name
from backend.app.verifiers.rule_support import evaluate_rule_support, unable_to_evaluate
from backend.app.verifiers.url_classifier import classify_url
from backend.app.verifiers.live_source import verify_live_source
from backend.app.verifiers.source_search import search_elitigation


def run_audit(request: AuditRequest) -> AuditResponse:
    connection = connect(settings.absolute_db_path)
    initialize_schema(connection)
    corpus = current_corpus(connection)
    extracted = extract_citations(request.response_text)
    known_cases = [dict(row) for row in connection.execute("SELECT * FROM cases").fetchall()]
    known_source_urls = [item["source_url"] for item in known_cases if item.get("source_url")]
    audits: list[CitationAudit] = []
    for citation in extracted:
        link_resolution = resolve_links(citation, request.links)
        href = link_resolution.href
        url_result = classify_url(href, known_source_urls)
        existence = (
            verify_parallel_existence(connection, citation.provided_name, citation.parallel_citations)
            if citation.parallel_citations
            else verify_existence(connection, citation.provided_name, citation.provided_citation)
        )
        case = existence.case
        name_matches, name_status = verify_name(citation.provided_name, case)
        link_status = (
            "LINK_SPLIT_OR_AMBIGUOUS"
            if link_resolution.status == "AMBIGUOUS"
            else verify_link(href, case, known_cases)
        )
        if case and settings.rule_evaluator == "heuristic":
            support = evaluate_rule_support(connection, case["case_id"], citation.surrounding_sentence, settings.max_evidence)
        elif case:
            support = unable_to_evaluate(f"Rule evaluator '{settings.rule_evaluator}' is not enabled in this first iteration.")
        else:
            support = unable_to_evaluate("No unique corpus case was resolved, so rule support cannot be evaluated.")
        live_verification = None
        source_discovery = None
        resolved_url = url_result.normalized_url
        expected = {
            "canonical_name": case["canonical_name"] if case else citation.provided_name,
        }
        if case:
            expected.update({
                "neutral_citation": case.get("neutral_citation"),
                "court": case.get("court"),
                "court_code": case.get("court_code"),
                "decision_date": case.get("decision_date"),
            })
        elif citation.provided_citation:
            expected["neutral_citation"] = citation.provided_citation
        expected = {key: value for key, value in expected.items() if value}
        if settings.enable_live_verification and url_result.normalized_url and url_result.status not in {
            "OFFICIAL_SOURCE_SEARCH_PAGE",
            "TRUSTED_PUBLISHER_SEARCH_PAGE",
            "MALFORMED_URL",
        }:
            if expected.get("canonical_name"):
                live_result = verify_live_source(url_result.normalized_url, expected)
                live_verification = LiveVerifyResponse(**live_result.__dict__)
                source_discovery = "DIRECT_LINK"
        elif settings.enable_live_verification and not href and expected.get("canonical_name"):
            search_result = search_elitigation(
                expected.get("canonical_name"),
                expected.get("neutral_citation"),
            )
            best_result = None
            for candidate in search_result.candidates:
                candidate_result = verify_live_source(candidate.url, expected)
                if best_result is None or candidate_result.source_verified:
                    best_result = candidate_result
                if candidate_result.source_verified:
                    break
            if best_result is not None:
                live_verification = LiveVerifyResponse(**best_result.__dict__)
                resolved_url = best_result.final_url
                source_discovery = "OFFICIAL_ELITIGATION_SEARCH"
                if resolved_url:
                    url_result = classify_url(resolved_url, known_source_urls)
        live_verified = bool(live_verification and live_verification.status == "LIVE_VERIFIED")
        live_mismatch = bool(live_verification and live_verification.status == "LIVE_METADATA_MISMATCH")
        status = "LIVE_METADATA_MISMATCH" if live_mismatch else citation_status(
            existence.status,
            name_matches,
            link_status,
            support.classification,
            live_verified,
        )
        needs_review = status not in {"VERIFIED_EXISTS", "LIVE_VERIFIED"} or support.needs_human_review
        explanation_prefix = (
            "LIVE_VERIFIED."
            if live_verified
            else "LIVE_METADATA_MISMATCH. The discovered source did not match the cited case metadata."
            if live_mismatch
            else existence.status + "."
        )
        audits.append(CitationAudit(
            occurrence_id=citation.occurrence_id,
            raw_text=citation.raw_text,
            provided_name=citation.provided_name,
            provided_citation=citation.provided_citation,
            parallel_citations=citation.parallel_citations,
            context_type=citation.context_type,
            footnote_number=citation.footnote_number,
            surrounding_sentence=citation.surrounding_sentence,
            canonical_name=case["canonical_name"] if case else (live_verification.case_name if live_verification else None),
            case_id=case["case_id"] if case else None,
            source_url=case["source_url"] if case else None,
            source_status=url_result.status if resolved_url else None,
            source_url_normalized=resolved_url,
            source_discovery=source_discovery,
            live_verification=live_verification,
            case_exists=case is not None and existence.status == "VERIFIED_EXISTS",
            existence_status=existence.status,
            name_matches=name_matches,
            name_status=name_status,
            link_status=link_status,
            rule_support=support.classification,
            rule_confidence=support.confidence,
            explanation=explanation_prefix + " " + url_result.reason + " " + support.explanation,
            evidence=[Evidence(**item) for item in support.evidence],
            candidates=(existence.candidates or [])[:5],
            needs_human_review=needs_review,
            status=status,
        ))
    connection.close()
    summary = AuditSummary(
        total_citations=len(audits),
        verified_cases=sum(item.case_exists or bool(item.live_verification and item.live_verification.source_verified) for item in audits),
        name_mismatches=sum(item.name_matches is False for item in audits),
        not_found=sum(item.existence_status == "NOT_FOUND_IN_VERIFIED_CORPUS" and not bool(item.live_verification and item.live_verification.source_verified) for item in audits),
        link_errors=sum(item.link_status in {"LINK_RESOLVES_TO_DIFFERENT_CASE", "LINK_BROKEN_OR_INACCESSIBLE", "LINK_POINTS_TO_SEARCH_RESULTS", "LINK_SPLIT_OR_AMBIGUOUS"} for item in audits),
        unsupported_rules=sum(item.rule_support == "UNSUPPORTED" for item in audits),
    )
    overall = "PASS" if audits and all(item.status in {"VERIFIED_EXISTS", "LIVE_VERIFIED"} and not item.needs_human_review for item in audits) else ("NO_CITATIONS" if not audits else "REVIEW_REQUIRED")
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
