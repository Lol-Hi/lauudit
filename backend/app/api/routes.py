from fastapi import APIRouter, Response

from backend.app.pipeline import run_audit
from backend.app.schemas import AuditRequest, AuditResponse

router = APIRouter()


@router.get("/")
def root() -> dict:
    return {
        "service": "Lauudit",
        "status": "ok",
        "health": "/health",
        "audit": "/api/v1/audit",
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
