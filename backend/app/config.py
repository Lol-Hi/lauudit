from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    root: Path = ROOT
    db_path: Path = Path(os.getenv("AUDIT_DB_PATH", "data/corpus/index.sqlite3"))
    cases_path: Path = Path(os.getenv("CORPUS_CASES_PATH", "data/corpus/cases.jsonl"))
    rule_evaluator: str = os.getenv("RULE_EVALUATOR", "heuristic").lower()
    max_evidence: int = int(os.getenv("AUDIT_MAX_EVIDENCE", "3"))

    def absolute(self, path: Path) -> Path:
        return path if path.is_absolute() else self.root / path

    @property
    def absolute_db_path(self) -> Path:
        return self.absolute(self.db_path)

    @property
    def absolute_cases_path(self) -> Path:
        return self.absolute(self.cases_path)


settings = Settings()

