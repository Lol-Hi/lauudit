import json
from pathlib import Path
from typing import Optional

import pytest

from backend.app.corpus.database import connect
from backend.app.corpus.indexer import build_index
from backend.app.corpus.search import paragraphs_for_case
from backend.app.verifiers.rule_support import evaluate_rule_support

pypdf = pytest.importorskip("pypdf")
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def _write_text_pdf(path: Path, pages: list[str]) -> None:
    writer = PdfWriter()
    for text in pages:
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject(
            {
                NameObject("/F1"): DictionaryObject(
                    {
                        NameObject("/Type"): NameObject("/Font"),
                        NameObject("/Subtype"): NameObject("/Type1"),
                        NameObject("/BaseFont"): NameObject("/Helvetica"),
                    }
                )
            }
        )
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): font})
        content = DecodedStreamObject()
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content.set_data(f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(content)
    with path.open("wb") as handle:
        writer.write(handle)


def _write_cases(path: Path, document_path: str, *, text_source: Optional[str] = None) -> None:
    record = {
        "case_id": "pdf-case",
        "canonical_name": "Lim v Tan",
        "aliases": [],
        "neutral_citation": "[2023] SGCA 12",
        "reported_citations": [],
        "court": "Court of Appeal",
        "court_code": "SGCA",
        "decision_date": "2023-01-01",
        "source_url": "https://www.elitigation.sg/gdviewer/s/2023_SGCA_12",
        "document_path": document_path,
        "source_type": "test",
    }
    if text_source is not None:
        record["text_source"] = text_source
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")


def test_native_pdf_preserves_page_reference_and_paragraph_number(tmp_path: Path):
    documents = tmp_path / "corpus" / "documents"
    documents.mkdir(parents=True)
    _write_text_pdf(
        documents / "judgment.pdf",
        [
            "[42] The court held that contractual agreement is assessed objectively by the parties words and conduct.",
            "[45] The court requires proof of objective agreement before enforcing the obligation.",
        ],
    )
    cases = tmp_path / "corpus" / "cases.jsonl"
    _write_cases(cases, "documents/judgment.pdf")
    db = tmp_path / "index.sqlite3"

    build_index(cases, db)
    connection = connect(db)
    evidence = paragraphs_for_case(connection, "pdf-case", "contractual agreement assessed objectively", 3)
    support = evaluate_rule_support(
        connection,
        "pdf-case",
        "Lim v Tan held that contractual agreement is assessed objectively by the parties words and conduct.",
    )
    connection.close()

    assert evidence[0]["paragraph"] == 42
    assert evidence[0]["page"] == 1
    assert evidence[0]["text_source"] == "native_pdf"
    assert support.classification == "SUPPORTED"
    assert support.evidence[0]["page"] == 1


def test_ocr_pdf_is_explicitly_marked_in_evidence(tmp_path: Path):
    documents = tmp_path / "corpus" / "documents"
    documents.mkdir(parents=True)
    _write_text_pdf(
        documents / "ocr-judgment.pdf",
        ["[42] Background facts.", "[45] The court held that objective agreement requires proof."],
    )
    cases = tmp_path / "corpus" / "cases.jsonl"
    _write_cases(cases, "documents/ocr-judgment.pdf", text_source="ocr")
    db = tmp_path / "index.sqlite3"

    build_index(cases, db)
    connection = connect(db)
    evidence = paragraphs_for_case(connection, "pdf-case", "objective agreement requires proof", 3)
    connection.close()

    assert evidence[0]["paragraph"] == 45
    assert evidence[0]["page"] == 2
    assert evidence[0]["text_source"] == "ocr"


def test_scanned_pdf_without_text_layer_fails_clearly(tmp_path: Path):
    documents = tmp_path / "corpus" / "documents"
    documents.mkdir(parents=True)
    _write_text_pdf(documents / "scanned.pdf", [""])
    cases = tmp_path / "corpus" / "cases.jsonl"
    _write_cases(cases, "documents/scanned.pdf")

    with pytest.raises(ValueError, match="no extractable text"):
        build_index(cases, tmp_path / "index.sqlite3")
