from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import uuid
from typing import Optional

import httpx

from backend.app.config import settings
from backend.app.corpus.database import connect, current_corpus, initialize_schema
from backend.app.extractors.citations import extract_citations
from backend.app.extractors.links import resolve_links
from backend.app.scoring import citation_status
from backend.app.schemas import AuditRequest, AuditResponse, AuditSummary, CitationAudit, Evidence, LiveVerifyResponse
from backend.app.verifiers.existence import ExistenceResult, verify_existence, verify_parallel_existence
from backend.app.verifiers.link_match import verify_link
from backend.app.verifiers.name_match import verify_name
from backend.app.verifiers.rule_support import evaluate_rule_support, unable_to_evaluate
from backend.app.verifiers.url_classifier import classify_url
from backend.app.verifiers.live_source import verify_live_source
from backend.app.verifiers.live_cache import cached_verify_live_candidate
from backend.app.verifiers.circuit_breaker import CircuitBreaker
from backend.app.verifiers.source_search import search_elitigation
from backend.app.normalization.case_names import name_matches_canonical


elitigation_breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=60.0)


def _record_live_verification_outcome(result: LiveVerifyResponse) -> None:
    """Trip only for transport failures, not valid negative verification results."""
    if result.status == "LIVE_SOURCE_UNAVAILABLE" and result.reason.startswith("Live fetch failed:"):
        elitigation_breaker.record_failure()
    else:
        elitigation_breaker.record_success()


def _verified_live_candidate(url: str, expected: dict) -> LiveVerifyResponse:
    result = cached_verify_live_candidate(url, expected, verifier=verify_live_source)
    _record_live_verification_outcome(result)
    return result


def _resolve_elitigation(citation, href: Optional[str], url_result, *, enabled: bool):
    """Resolve the cited judgment from eLitigation before consulting local data."""
    if not enabled or elitigation_breaker.is_open():
        return None, None, None

    expected = {}
    if citation.provided_citation:
        # A neutral citation uniquely identifies the judgment and avoids
        # rejecting a real source because the browser extracted an incomplete
        # or wrapped party name.
        expected["neutral_citation"] = citation.provided_citation
    elif citation.provided_name:
        expected["canonical_name"] = citation.provided_name
    if not expected:
        return None, None, None

    live_verification = None
    source_discovery = None
    resolved_url = None
    try:
        if url_result.status == "OFFICIAL_ELITIGATION_SOURCE":
            live_verification = _verified_live_candidate(url_result.normalized_url, expected)
            source_discovery = "DIRECT_ELITIGATION_LINK"
            resolved_url = live_verification.final_url or url_result.normalized_url

        if not live_verification or not live_verification.source_verified:
            search_result = search_elitigation(citation.provided_name, citation.provided_citation)
            if search_result.request_failed:
                elitigation_breaker.record_failure()
            else:
                elitigation_breaker.record_success()
            candidates = []
            for candidate in search_result.candidates:
                candidate_result = _verified_live_candidate(candidate.url, expected)
                candidates.append(candidate_result)
                if candidate_result.source_verified:
                    live_verification = candidate_result
                    resolved_url = candidate_result.final_url or candidate.url
                    source_discovery = "OFFICIAL_ELITIGATION_SEARCH"
                    break
            if live_verification is None and candidates:
                live_verification = candidates[0]
                resolved_url = live_verification.final_url
                source_discovery = "OFFICIAL_ELITIGATION_SEARCH"
    except (TimeoutError, ConnectionError, httpx.HTTPError):
        elitigation_breaker.record_failure()
        return None, None, None

    return live_verification, resolved_url, source_discovery


def run_audit(request: AuditRequest) -> AuditResponse:
    live_authority = settings.enable_live_verification and request.enable_live_verification is not False
    connection = None
    corpus = None
    if not live_authority:
        connection = connect(settings.absolute_db_path)
        initialize_schema(connection)
        corpus = current_corpus(connection)
    response_for_extraction = request.response_markdown or request.response_text
    extracted = extract_citations(response_for_extraction)
    known_cases = [] if live_authority else [dict(row) for row in connection.execute("SELECT * FROM cases").fetchall()]
    known_source_urls = [item["source_url"] for item in known_cases if item.get("source_url")]
    citation_contexts = [
        (citation, resolve_links(citation, request.links))
        for citation in extracted
    ]
    citation_contexts = [
        (citation, link_resolution, classify_url(link_resolution.href, known_source_urls))
        for citation, link_resolution in citation_contexts
    ]
    live_resolutions = []
    if live_authority and citation_contexts:
        def resolve_live_context(context):
            citation, link_resolution, url_result = context
            return _resolve_elitigation(
                citation,
                link_resolution.href,
                url_result,
                enabled=True,
            )

        with ThreadPoolExecutor(max_workers=min(8, len(citation_contexts))) as pool:
            live_resolutions = list(pool.map(resolve_live_context, citation_contexts))

    audits: list[CitationAudit] = []
    for index, (citation, link_resolution, url_result) in enumerate(citation_contexts):
        href = link_resolution.href
        existence = ExistenceResult("SOURCE_UNAVAILABLE") if live_authority else (
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
        if live_authority:
            support = unable_to_evaluate(
                "Rule support is not inferred from the local corpus; eLitigation authenticity does not itself prove the legal proposition."
            )
        elif case and settings.rule_evaluator == "heuristic":
            support = evaluate_rule_support(connection, case["case_id"], citation.surrounding_sentence, settings.max_evidence)
        elif case:
            support = unable_to_evaluate(f"Rule evaluator '{settings.rule_evaluator}' is not enabled in this deployment.")
        else:
            support = unable_to_evaluate("No unique corpus case was resolved, so rule support cannot be evaluated.")
        live_verification = None
        source_discovery = None
        resolved_url = url_result.normalized_url
        supplied_url = url_result.normalized_url
        if live_authority:
            live_verification, resolved_url, source_discovery = live_resolutions[index]
            if resolved_url:
                url_result = classify_url(resolved_url, [])
            if live_verification and live_verification.source_verified:
                existence = ExistenceResult("VERIFIED_EXISTS", method="official_elitigation")
                case = None
                name_matches = (
                    name_matches_canonical(citation.provided_name, live_verification.case_name)
                    if citation.provided_name and live_verification.case_name
                    else None
                )
                name_status = "CANONICAL_NAME_MATCH" if name_matches is True else (
                    "VERIFIED_EXISTS_NAME_MISMATCH" if name_matches is False else "NAME_NOT_PROVIDED"
                )
                link_status = "NO_LINK_AVAILABLE" if not href else (
                    "LINK_CONFIRMS_CASE"
                    if source_discovery == "DIRECT_ELITIGATION_LINK" and supplied_url == resolved_url
                    else "LINK_BROKEN_OR_INACCESSIBLE"
                )
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
            text_start=citation.start,
            text_end=citation.end,
            provided_name=citation.provided_name,
            provided_citation=citation.provided_citation,
            parallel_citations=citation.parallel_citations,
            context_type=citation.context_type,
            footnote_number=citation.footnote_number,
            surrounding_sentence=citation.surrounding_sentence,
            canonical_name=case["canonical_name"] if case else (live_verification.case_name if live_verification else None),
            case_id=case["case_id"] if case else None,
            source_url=case["source_url"] if case else (live_verification.final_url if live_verification else None),
            source_status=url_result.status if resolved_url else None,
            source_url_normalized=resolved_url,
            source_discovery=source_discovery,
            live_verification=live_verification,
            case_exists=(case is not None and existence.status == "VERIFIED_EXISTS") or live_verified,
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
    if connection is not None:
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
        corpus_snapshot=corpus["snapshot_id"] if corpus else "elitigation-live",
        corpus_completeness=corpus["completeness"] if corpus else "official-live",
        corpus_notes=corpus["notes"] if corpus else "Official eLitigation is authoritative for this audit; the local corpus was not consulted.",
        overall_status=overall,
        summary=summary,
        citations=audits,
        capture_diagnostics=request.capture_diagnostics,
        verification_authority="elitigation" if live_authority else "local_corpus",
    )
