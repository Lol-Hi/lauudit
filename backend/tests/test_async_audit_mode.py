from dataclasses import replace

from fastapi.testclient import TestClient

from backend.app import pipeline
from backend.app.main import app


def test_audit_request_can_override_live_verification_mode(monkeypatch, indexed_db):
    monkeypatch.setattr(
        pipeline,
        "settings",
        replace(pipeline.settings, enable_live_verification=True),
    )

    def fail_live_verification(*args, **kwargs):
        raise AssertionError("the local-first request must not contact eLitigation")

    monkeypatch.setattr(pipeline, "verify_live_source", fail_live_verification)
    response = TestClient(app).post(
        "/api/v1/audit",
        json={
            "response_text": "Lim v Tan [2023] SGCA 12 held that agreement is assessed objectively.",
            "enable_live_verification": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["verification_authority"] == "local_corpus"
    assert body["corpus_snapshot"].startswith("snapshot-")


def test_request_cannot_enable_live_verification_when_deployment_disables_it(monkeypatch, indexed_db):
    monkeypatch.setattr(
        pipeline,
        "settings",
        replace(pipeline.settings, enable_live_verification=False),
    )

    def fail_live_verification(*args, **kwargs):
        raise AssertionError("deployment-level live verification must remain authoritative")

    monkeypatch.setattr(pipeline, "verify_live_source", fail_live_verification)
    response = TestClient(app).post(
        "/api/v1/audit",
        json={
            "response_text": "Lim v Tan [2023] SGCA 12 held that agreement is assessed objectively.",
            "enable_live_verification": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["verification_authority"] == "local_corpus"
