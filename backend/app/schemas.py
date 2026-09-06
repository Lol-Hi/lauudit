from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class LinkInput(BaseModel):
    text: str = ""
    href: str
    context: str = ""
    block_id: Optional[str] = None
    mapping_status: Optional[Literal["EXACT", "UNMAPPED"]] = None
    start: Optional[int] = Field(default=None, ge=0)
    end: Optional[int] = Field(default=None, ge=0)


class ContentBlock(BaseModel):
    id: str
    tag: str
    text: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)


class AuditRequest(BaseModel):
    response_text: str = Field(min_length=1)
    response_markdown: Optional[str] = Field(default=None, min_length=1)
    response_format: Literal["plain_text", "markdown"] = "plain_text"
    links: list[LinkInput] = Field(default_factory=list)
    content_blocks: list[ContentBlock] = Field(default_factory=list)
    candidate_regions: list[dict[str, Any]] = Field(default_factory=list)
    excluded_regions: list[dict[str, Any]] = Field(default_factory=list)
    capture_diagnostics: dict[str, Any] = Field(default_factory=dict)
    page_url: Optional[str] = None
    user_query: Optional[str] = None
    jurisdiction: str = "Singapore"
    as_of_date: Optional[str] = None
    enable_live_verification: Optional[bool] = None


class ExpectedMetadata(BaseModel):
    canonical_name: str = Field(min_length=1)
    neutral_citation: Optional[str] = None
    court: Optional[str] = None
    court_code: Optional[str] = None
    decision_date: Optional[str] = None


class LiveVerifyRequest(BaseModel):
    source_url: str = Field(min_length=1)
    expected: ExpectedMetadata


class LiveVerifyResponse(BaseModel):
    status: str
    attempted: bool
    source_verified: bool
    final_url: Optional[str] = None
    retrieved_at: Optional[str] = None
    metadata_match: dict[str, Optional[bool]] = Field(default_factory=dict)
    case_name: Optional[str] = None
    neutral_citation: Optional[str] = None
    court_code: Optional[str] = None
    decision_date: Optional[str] = None
    reason: str = ""


class Evidence(BaseModel):
    paragraph: int
    text: str
    score: Optional[float] = None
    page: Optional[int] = None
    text_source: str = "plain_text"


RuleStatus = Literal["SUPPORTED", "UNSUPPORTED", "UNCERTAIN", "UNABLE_TO_EVALUATE"]
LinkStatus = Literal[
    "LINK_CONFIRMS_CASE",
    "LINK_RESOLVES_TO_DIFFERENT_CASE",
    "LINK_BROKEN_OR_INACCESSIBLE",
    "LINK_POINTS_TO_SEARCH_RESULTS",
    "LINK_SPLIT_OR_AMBIGUOUS",
    "NO_LINK_AVAILABLE",
]
SourceStatus = Literal[
    "KNOWN_CORPUS_SOURCE",
    "OFFICIAL_ELITIGATION_SOURCE",
    "OFFICIAL_JUDICIARY_SOURCE",
    "OFFICIAL_SOURCE_SEARCH_PAGE",
    "TRUSTED_PUBLISHER_SOURCE",
    "TRUSTED_PUBLISHER_SEARCH_PAGE",
    "UNVERIFIED_EXTERNAL_URL",
    "MALFORMED_URL",
]
ExistenceStatus = Literal[
    "VERIFIED_EXISTS",
    "NOT_FOUND_IN_VERIFIED_CORPUS",
    "AMBIGUOUS_MATCH",
    "SOURCE_UNAVAILABLE",
]


class CitationAudit(BaseModel):
    occurrence_id: str
    raw_text: str
    text_start: int = Field(default=0, ge=0)
    text_end: int = Field(default=0, ge=0)
    provided_name: Optional[str] = None
    provided_citation: Optional[str] = None
    parallel_citations: list[str] = Field(default_factory=list)
    context_type: str = "body"
    footnote_number: Optional[str] = None
    surrounding_sentence: str
    canonical_name: Optional[str] = None
    case_id: Optional[str] = None
    source_url: Optional[str] = None
    source_status: Optional[SourceStatus] = None
    source_url_normalized: Optional[str] = None
    source_discovery: Optional[str] = None
    live_verification: Optional[LiveVerifyResponse] = None
    case_exists: bool = False
    existence_status: ExistenceStatus
    name_matches: Optional[bool] = None
    name_status: Optional[str] = None
    link_status: LinkStatus
    rule_support: RuleStatus
    rule_confidence: float = 0.0
    explanation: str
    evidence: list[Evidence] = Field(default_factory=list)
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    needs_human_review: bool = True
    status: str


class AuditSummary(BaseModel):
    total_citations: int
    verified_cases: int
    name_mismatches: int
    not_found: int
    link_errors: int
    unsupported_rules: int


class AuditResponse(BaseModel):
    audit_id: str
    jurisdiction: str
    corpus_snapshot: str
    corpus_completeness: str = "unknown"
    corpus_notes: str = ""
    overall_status: str
    summary: AuditSummary
    citations: list[CitationAudit]
    capture_diagnostics: dict[str, Any] = Field(default_factory=dict)
    verification_authority: Literal["elitigation", "local_corpus"] = "local_corpus"
    disclaimer: str = "This tool is an audit aid, not legal advice. Human review is required."
