import json
import os
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from backend.app import pipeline
from backend.app.config import settings
from backend.app.corpus.indexer import build_index
from backend.app.main import app


LIVE_VIEWER_URL = "https://www.elitigation.sg/gdviewer/s/2026_SGCA_39"
LIVE_PDF_URL = "https://www.elitigation.sg/gdviewer/gd/2026_SGCA_39/pdf"
CASE_NAME = "Howe Wen Khong Rocky and others v Attorney-General"


@pytest.mark.live
@pytest.mark.skipif(
    os.getenv("RUN_LIVE_TESTS") != "1",
    reason="Set RUN_LIVE_TESTS=1 after confirming the source is permitted and reachable.",
)
def test_real_elitigation_pdf_to_audit_payload(tmp_path: Path, monkeypatch):
    """Exercise the real eLitigation PDF through indexing and the audit API."""
    with httpx.Client(
        follow_redirects=True,
        timeout=20.0,
        headers={"User-Agent": "Lauudit-Phase7-LiveTest/0.1 (read-only)"},
    ) as client:
        pdf_response = client.get(LIVE_PDF_URL)

    assert pdf_response.is_success
    assert "application/pdf" in pdf_response.headers.get("content-type", "").lower()
    pdf_path = tmp_path / "judgment.pdf"
    pdf_path.write_bytes(pdf_response.content)

    first_page_text = (PdfReader(str(pdf_path)).pages[0].extract_text() or "")
    assert "[2026] SGCA 39" in first_page_text
    assert "Howe Wen Khong Rocky" in first_page_text

    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(
        json.dumps(
            {
                "case_id": "elitigation-2026-sgca-39",
                "canonical_name": CASE_NAME,
                "aliases": [],
                "neutral_citation": "[2026] SGCA 39",
                "reported_citations": [],
                "court": "Court of Appeal",
                "court_code": "SGCA",
                "decision_date": "2026-09-03",
                "source_url": LIVE_PDF_URL,
                "document_path": str(pdf_path),
                "source_type": "elitigation_pdf",
                "text_source": "native_pdf",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "index.sqlite3"
    build_index(cases_path, db_path)
    monkeypatch.setattr(
        pipeline,
        "settings",
        replace(settings, root=tmp_path, db_path=db_path, cases_path=cases_path),
    )

    frontend_request = {
        "response_text": (
            f"{CASE_NAME} [2026] SGCA 39 held that the principle of standing requires an applicant "
            "to show that a public right was violated and that the applicant suffered special damage."
        ),
        "links": [
            {
                "text": f"{CASE_NAME} [2026] SGCA 39",
                "href": LIVE_PDF_URL,
                "context": f"{CASE_NAME} [2026] SGCA 39 held that the principle of standing requires special damage.",
            }
        ],
        "page_url": LIVE_VIEWER_URL,
        "user_query": None,
        "jurisdiction": "Singapore",
        "as_of_date": "2026-09-06",
    }
    response = TestClient(app).post("/api/v1/audit", json=frontend_request)

    assert response.status_code == 200
    citation = response.json()["citations"][0]
    assert citation["case_id"] == "elitigation-2026-sgca-39"
    assert citation["case_exists"] is True
    assert citation["source_status"] == "KNOWN_CORPUS_SOURCE"
    assert citation["link_status"] == "LINK_CONFIRMS_CASE"
    assert citation["evidence"]
    assert citation["evidence"][0]["page"] >= 1
    assert citation["evidence"][0]["text_source"] == "native_pdf"
