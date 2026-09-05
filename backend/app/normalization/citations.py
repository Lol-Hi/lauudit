from __future__ import annotations

import re


def normalize_citation(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().upper())

