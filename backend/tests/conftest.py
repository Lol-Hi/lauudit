from pathlib import Path

import pytest

from backend.app.config import Settings
from backend.app.corpus.indexer import build_index


@pytest.fixture
def indexed_db(tmp_path: Path, monkeypatch):
    corpus = tmp_path / "corpus"
    docs = corpus / "documents"
    docs.mkdir(parents=True)
    (docs / "case.txt").write_text(
        "[42] The court held that contractual agreement is assessed objectively by the parties' words and conduct.\n\n"
        "[45] The court requires proof of objective agreement before enforcing the obligation.\n",
        encoding="utf-8",
    )
    cases = corpus / "cases.jsonl"
    cases.write_text(
        '{"case_id":"case-1","canonical_name":"Lim v Tan","aliases":["Tan v Lim"],"neutral_citation":"[2023] SGCA 12","reported_citations":["[2023] 2 SLR 100"],"court":"Court of Appeal","court_code":"SGCA","decision_date":"2023-01-01","source_url":"https://official.test/case-1","document_path":"documents/case.txt","source_type":"test"}\n',
        encoding="utf-8",
    )
    db = tmp_path / "index.sqlite3"
    build_index(cases, db)
    monkeypatch.setattr("backend.app.pipeline.settings", Settings(root=tmp_path, db_path=db, cases_path=cases))
    return db
