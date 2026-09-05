from __future__ import annotations

import re
from typing import Optional


_WS = re.compile(r"\s+")


def normalize_case_name(value: str) -> str:
    """Normalize names for comparison while retaining every substantive word."""
    value = value.strip().upper()
    value = value.replace("VERSUS", " V ").replace("V.", " V ")
    value = re.sub(r"\bPP\b", "PUBLIC PROSECUTOR", value)
    value = value.replace("&", " AND ")
    value = re.sub(r"[\u2018\u2019]", "'", value)
    value = re.sub(r"[^A-Z0-9']+", " ", value)
    return _WS.sub(" ", value).strip()


def name_matches_canonical(provided: Optional[str], canonical: Optional[str]) -> Optional[bool]:
    if not provided or not canonical:
        return None
    return normalize_case_name(provided) == normalize_case_name(canonical)
