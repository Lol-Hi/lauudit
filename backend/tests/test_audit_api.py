from fastapi.testclient import TestClient

from backend.app.main import app


def test_audit_api(indexed_db):
    client = TestClient(app)
    root = client.get("/")
    assert root.status_code == 200
    assert root.json()["service"] == "Lauudit"
    assert client.get("/favicon.ico").status_code == 204
    response = client.post("/api/v1/audit", json={
        "response_text": "Tan v Lim [2023] SGCA 12 held that contractual agreement is assessed objectively.",
        "links": [{"text": "Tan v Lim [2023] SGCA 12", "href": "https://official.test/case-1", "context": "Tan v Lim [2023] SGCA 12 held..."}],
        "page_url": "http://localhost",
        "as_of_date": "2026-09-05",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["total_citations"] == 1
    assert body["citations"][0]["canonical_name"] == "Lim v Tan"
    assert body["citations"][0]["name_matches"] is False
    assert body["citations"][0]["link_status"] == "LINK_CONFIRMS_CASE"
    assert body["citations"][0]["source_status"] == "KNOWN_CORPUS_SOURCE"
    assert body["citations"][0]["source_url_normalized"] == "https://official.test/case-1"
