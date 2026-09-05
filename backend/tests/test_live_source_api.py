from dataclasses import replace

import httpx
from fastapi.testclient import TestClient

from backend.app.api import routes
from backend.app import pipeline
from backend.app.config import settings
from backend.app.main import app
from backend.app.verifiers.live_source import verify_live_source


JUDGMENT_HTML = """
<html><body>
<div class="HN-NeutralCit"><span>[2023] SGCA 12</span></div>
<div class="HN-CaseName"><span>Lim v Tan</span></div>
<div class="CaseNumber">Court of Appeal / Civil Appeal No 12 of 2023</div>
<div class="Judg-Date-Reserved">1 January 2023</div>
</body></html>
"""


def _mocked_verifier(source_url: str, expected: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text=JUDGMENT_HTML,
        )

    transport = httpx.MockTransport(handler)
    return verify_live_source(
        source_url,
        expected,
        client_factory=lambda **kwargs: httpx.Client(transport=transport, **kwargs),
    )


def test_live_verify_api_is_disabled_by_default(monkeypatch):
    monkeypatch.setattr(
        routes,
        "settings",
        replace(settings, enable_live_verification=False),
    )

    def fail(*args, **kwargs):
        raise AssertionError("disabled endpoint must not call the verifier")

    monkeypatch.setattr(routes, "verify_live_source", fail)
    response = TestClient(app).post(
        "/api/v1/sources/verify",
        json={
            "source_url": "https://www.elitigation.sg/gdviewer/s/2023_SGCA_12",
            "expected": {"canonical_name": "Lim v Tan"},
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "LIVE_VERIFICATION_DISABLED",
        "attempted": False,
        "source_verified": False,
        "final_url": None,
        "retrieved_at": None,
        "metadata_match": {},
        "case_name": None,
        "neutral_citation": None,
        "court_code": None,
        "decision_date": None,
        "reason": "Live verification is disabled on this deployment.",
    }


def test_live_verify_api_returns_ephemeral_metadata_result(monkeypatch):
    monkeypatch.setattr(
        routes,
        "settings",
        replace(settings, enable_live_verification=True),
    )
    monkeypatch.setattr(routes, "verify_live_source", _mocked_verifier)

    response = TestClient(app).post(
        "/api/v1/sources/verify",
        json={
            "source_url": "https://www.elitigation.sg/gdviewer/s/2023_SGCA_12",
            "expected": {
                "canonical_name": "Lim v Tan",
                "neutral_citation": "[2023] SGCA 12",
                "court": "Court of Appeal",
                "decision_date": "2023-01-01",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "LIVE_VERIFIED"
    assert body["source_verified"] is True
    assert body["metadata_match"] == {
        "name": True,
        "citation": True,
        "court": True,
        "date": True,
    }
    assert body["case_name"] == "Lim v Tan"
    assert body["neutral_citation"] == "[2023] SGCA 12"


def test_live_verify_api_keeps_allowlist_enforcement_server_side(monkeypatch):
    monkeypatch.setattr(
        routes,
        "settings",
        replace(settings, enable_live_verification=True),
    )

    def no_network_factory(**kwargs):
        raise AssertionError("untrusted URL must not reach the network")

    # Exercise the actual verifier while preventing its HTTP client from being used.
    monkeypatch.setattr(
        routes,
        "verify_live_source",
        lambda source_url, expected: verify_live_source(
            source_url,
            expected,
            client_factory=no_network_factory,
        ),
    )

    response = TestClient(app).post(
        "/api/v1/sources/verify",
        json={
            "source_url": "https://example.com/case",
            "expected": {"canonical_name": "Lim v Tan"},
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "LIVE_VERIFICATION_SKIPPED_UNTRUSTED_HOST"
    assert response.json()["attempted"] is False


def test_phase3_payload_contract_is_accepted_by_phase4_endpoint(monkeypatch):
    """Exercise the payload shape documented for the future extension button."""
    monkeypatch.setattr(
        routes,
        "settings",
        replace(settings, enable_live_verification=True),
    )
    monkeypatch.setattr(routes, "verify_live_source", _mocked_verifier)

    phase3_payload = {
        "source_url": "https://www.elitigation.sg/gdviewer/s/2023_SGCA_12",
        "expected": {
            "canonical_name": "Lim v Tan",
            "neutral_citation": "[2023] SGCA 12",
            "court_code": "SGCA",
            "decision_date": "2023-01-01",
        },
    }
    response = TestClient(app).post("/api/v1/sources/verify", json=phase3_payload)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "LIVE_VERIFIED"
    assert body["metadata_match"] == {
        "name": True,
        "citation": True,
        "court_code": True,
        "date": True,
    }


def test_audit_path_automatically_verifies_allowlisted_direct_sources(monkeypatch, indexed_db):
    monkeypatch.setattr(
        routes,
        "settings",
        replace(settings, enable_live_verification=True),
    )
    monkeypatch.setattr(
        pipeline,
        "settings",
        replace(pipeline.settings, enable_live_verification=True),
    )
    monkeypatch.setattr(pipeline, "verify_live_source", _mocked_verifier)
    response = TestClient(app).post(
        "/api/v1/audit",
        json={
            "response_text": "Lim v Tan [2023] SGCA 12 held that contractual agreement is assessed objectively.",
            "links": [{
                "text": "Lim v Tan [2023] SGCA 12",
                "href": "https://www.elitigation.sg/gdviewer/s/2023_SGCA_12",
                "context": "Lim v Tan [2023] SGCA 12 held...",
            }],
        },
    )

    assert response.status_code == 200
    citation = response.json()["citations"][0]
    assert citation["source_status"] == "OFFICIAL_ELITIGATION_SOURCE"
    assert citation["live_verification"]["status"] == "LIVE_VERIFIED"
    assert citation["live_verification"]["attempted"] is True
