from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import pipeline
from backend.app.config import settings
from backend.app.corpus.indexer import build_index
from backend.app.main import app
from backend.tests.test_pdf_ingestion import _write_cases, _write_text_pdf


def test_extension_request_to_pdf_evidence_end_to_end(tmp_path: Path, monkeypatch):
    documents = tmp_path / "corpus" / "documents"
    documents.mkdir(parents=True)
    _write_text_pdf(
        documents / "judgment.pdf",
        [
            "[42] The court held that contractual agreement is assessed objectively by the parties words and conduct.",
        ],
    )
    cases = tmp_path / "corpus" / "cases.jsonl"
    _write_cases(cases, "documents/judgment.pdf")
    db = tmp_path / "index.sqlite3"
    build_index(cases, db)
    monkeypatch.setattr(
        pipeline,
        "settings",
        replace(settings, root=tmp_path, db_path=db, cases_path=cases, enable_live_verification=False),
    )

    # This mirrors the object produced by extension/src/content.js and sent by
    # the AUDIT_ACTIVE_TAB background message.
    frontend_request = {
        "response_text": "Lim v Tan [2023] SGCA 12 held that contractual agreement is assessed objectively by the parties words and conduct.",
        "links": [
            {
                "text": "Lim v Tan [2023] SGCA 12",
                "href": "https://www.elitigation.sg/gdviewer/s/2023_SGCA_12",
                "context": "Lim v Tan [2023] SGCA 12 held that contractual agreement is assessed objectively.",
            }
        ],
        "page_url": "https://chat.example.test/conversation/123",
        "user_query": None,
        "jurisdiction": "Singapore",
        "as_of_date": "2026-09-06",
    }

    response = TestClient(app).post("/api/v1/audit", json=frontend_request)

    assert response.status_code == 200
    body = response.json()
    citation = body["citations"][0]
    assert body["summary"]["total_citations"] == 1
    assert citation["case_id"] == "pdf-case"
    assert citation["case_exists"] is True
    assert citation["source_status"] == "KNOWN_CORPUS_SOURCE"
    assert citation["link_status"] == "LINK_CONFIRMS_CASE"
    assert citation["rule_support"] == "SUPPORTED"
    assert citation["evidence"][0]["paragraph"] == 42
    assert citation["evidence"][0]["page"] == 1
    assert citation["evidence"][0]["text_source"] == "native_pdf"
