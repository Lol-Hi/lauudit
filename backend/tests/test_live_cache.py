from dataclasses import dataclass
import time
from typing import Optional

from cachetools import TTLCache

import backend.app.verifiers.live_cache as live_cache
from backend.app.verifiers.live_cache import (
    cached_verify_live_candidate,
    clear_live_verification_cache,
)


@dataclass
class FakeResult:
    status: str
    attempted: bool
    source_verified: bool
    final_url: Optional[str] = None


def test_successful_live_verification_is_cached():
    clear_live_verification_cache()
    calls = 0

    def verifier(url, expected):
        nonlocal calls
        calls += 1
        return FakeResult("LIVE_VERIFIED", True, True, url)

    first = cached_verify_live_candidate(
        "https://www.elitigation.sg/gdviewer/s/2023_SGCA_12/",
        {"neutral_citation": "[2023] SGCA 12", "canonical_name": "Lim v Tan"},
        verifier=verifier,
    )
    second = cached_verify_live_candidate(
        "https://www.elitigation.sg/gdviewer/s/2023_SGCA_12",
        {"canonical_name": "Lim v Tan", "neutral_citation": "[2023] SGCA 12"},
        verifier=verifier,
    )

    assert calls == 1
    assert first.status == second.status == "LIVE_VERIFIED"


def test_unsuccessful_live_verification_is_not_cached():
    clear_live_verification_cache()
    calls = 0

    def verifier(url, expected):
        nonlocal calls
        calls += 1
        return FakeResult("LIVE_METADATA_MISMATCH", True, False)

    cached_verify_live_candidate(
        "https://www.elitigation.sg/gdviewer/s/2023_SGCA_12",
        {"canonical_name": "Wrong Name"},
        verifier=verifier,
    )
    cached_verify_live_candidate(
        "https://www.elitigation.sg/gdviewer/s/2023_SGCA_12",
        {"canonical_name": "Wrong Name"},
        verifier=verifier,
    )

    assert calls == 2


def test_successful_live_verification_expires(monkeypatch):
    monkeypatch.setattr(live_cache, "_cache", TTLCache(maxsize=10, ttl=0.01))
    clear_live_verification_cache()
    calls = 0

    def verifier(url, expected):
        nonlocal calls
        calls += 1
        return FakeResult("LIVE_VERIFIED", True, True, url)

    cached_verify_live_candidate(
        "https://www.elitigation.sg/gdviewer/s/2023_SGCA_12",
        {"canonical_name": "Lim v Tan"},
        verifier=verifier,
    )
    time.sleep(0.03)
    cached_verify_live_candidate(
        "https://www.elitigation.sg/gdviewer/s/2023_SGCA_12",
        {"canonical_name": "Lim v Tan"},
        verifier=verifier,
    )

    assert calls == 2
