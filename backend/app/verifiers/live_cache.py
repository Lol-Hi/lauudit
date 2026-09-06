"""Small in-process cache for successful live source verifications."""

from __future__ import annotations

from threading import RLock
from typing import Any, Callable

from cachetools import TTLCache

from backend.app.schemas import LiveVerifyResponse
from backend.app.verifiers.url_classifier import normalize_url


LIVE_VERIFICATION_CACHE_MAXSIZE = 2_000
LIVE_VERIFICATION_CACHE_TTL_SECONDS = 60 * 60

_cache: TTLCache = TTLCache(
    maxsize=LIVE_VERIFICATION_CACHE_MAXSIZE,
    ttl=LIVE_VERIFICATION_CACHE_TTL_SECONDS,
)
_cache_lock = RLock()


def _cache_key(url: str, expected: dict[str, Any]) -> tuple[str, tuple[tuple[str, str], ...]]:
    try:
        normalized_url = normalize_url(url)
    except (TypeError, ValueError):
        # Let the verifier retain responsibility for invalid URL responses, while
        # still producing a deterministic key if it is called with one.
        normalized_url = url.strip()

    expected_key = tuple(
        sorted(
            (str(name), "" if value is None else str(value).strip())
            for name, value in expected.items()
        )
    )
    return normalized_url, expected_key


def clear_live_verification_cache() -> None:
    """Clear cached results, primarily for tests and local development."""
    with _cache_lock:
        _cache.clear()


def cached_verify_live_candidate(
    url: str,
    expected: dict[str, Any],
    *,
    verifier: Callable[[str, dict[str, Any]], Any],
) -> LiveVerifyResponse:
    """Return a cached successful verification or perform a fresh lookup.

    Failed, unavailable, and metadata-mismatch responses are deliberately not
    cached so a temporary source problem or a later source correction can be
    observed on the next audit.
    """
    key = _cache_key(url, expected)
    with _cache_lock:
        cached = _cache.get(key)
    if cached is not None:
        return cached.model_copy(deep=True)

    result = LiveVerifyResponse(**verifier(url, expected).__dict__)
    if result.source_verified:
        with _cache_lock:
            _cache[key] = result.model_copy(deep=True)
    return result
