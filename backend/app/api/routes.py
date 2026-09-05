from dataclasses import asdict

from fastapi import APIRouter, Response

from backend.app.config import settings
from backend.app.pipeline import run_audit
from backend.app.schemas import AuditRequest, AuditResponse, LiveVerifyRequest, LiveVerifyResponse
from backend.app.verifiers.live_source import verify_live_source

router = APIRouter()


@router.get("/")
def root() -> dict:
    return {
        "service": "Lauudit",
        "status": "ok",
        "health": "/health",
        "audit": "/api/v1/audit",
        "live_source_verification": "/api/v1/sources/verify",
        "docs": "/docs",
    }


@router.get("/favicon.ico", status_code=204)
def favicon() -> Response:
    return Response(status_code=204)


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "local-singapore-legal-ai-citation-auditor"}


@router.post("/api/v1/audit", response_model=AuditResponse)
def audit(request: AuditRequest) -> AuditResponse:
    return run_audit(request)


@router.post("/api/v1/sources/verify", response_model=LiveVerifyResponse)
def verify_source(request: LiveVerifyRequest) -> LiveVerifyResponse:
    """Explicitly verify one allowlisted source without changing audit state."""
    if not settings.enable_live_verification:
        return LiveVerifyResponse(
            status="LIVE_VERIFICATION_DISABLED",
            attempted=False,
            source_verified=False,
            reason="Live verification is disabled on this deployment.",
        )

    result = verify_live_source(request.source_url, request.expected.model_dump())
    return LiveVerifyResponse(**asdict(result))
