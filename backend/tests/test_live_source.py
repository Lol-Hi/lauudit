import os

import httpx
import pytest

from backend.app.verifiers.live_source import verify_live_source


JUDGMENT_HTML = """
<html><body>
<div class="HN-NeutralCit"><span>[2023] SGCA 12</span></div>
<div class="HN-CaseName"><span>Lim v Tan</span></div>
<div class="CaseNumber">Court of Appeal / Civil Appeal No 12 of 2023</div>
<div class="Judg-Date-Reserved">1 January 2023</div>
</body></html>
"""


def client_factory(handler):
    transport = httpx.MockTransport(handler)

    def factory(**kwargs):
        return httpx.Client(transport=transport, **kwargs)

    return factory


def test_metadata_match_and_redirect_following():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/old"):
            return httpx.Response(302, headers={"location": "/gdviewer/s/2023_SGCA_12"})
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            text=JUDGMENT_HTML,
        )

    result = verify_live_source(
        "https://www.elitigation.sg/old",
        {
            "canonical_name": "Lim v Tan",
            "neutral_citation": "[2023] SGCA 12",
            "court": "Court of Appeal",
            "decision_date": "2023-01-01",
        },
        client_factory=client_factory(handler),
    )

    assert result.status == "LIVE_VERIFIED"
    assert result.source_verified is True
    assert result.final_url == "https://www.elitigation.sg/gdviewer/s/2023_SGCA_12"
    assert result.metadata_match == {"name": True, "citation": True, "court": True, "date": True}


def test_metadata_mismatch_is_not_verified():
    result = verify_live_source(
        "https://www.elitigation.sg/gdviewer/s/2023_SGCA_12",
        {"canonical_name": "Different v Case", "neutral_citation": "[2023] SGCA 12"},
        client_factory=client_factory(
            lambda request: httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text=JUDGMENT_HTML,
            )
        ),
    )

    assert result.status == "LIVE_METADATA_MISMATCH"
    assert result.source_verified is False
    assert result.metadata_match == {"name": False, "citation": True}


def test_untrusted_and_search_urls_are_not_fetched():
    def fail(request: httpx.Request) -> httpx.Response:
        raise AssertionError("untrusted URLs must not be fetched")

    external = verify_live_source(
        "https://example.com/case",
        {"canonical_name": "Lim v Tan"},
        client_factory=client_factory(fail),
    )
    search = verify_live_source(
        "https://www.elitigation.sg/gdviewer/Home/Index?SearchPhrase=case",
        {"canonical_name": "Lim v Tan"},
        client_factory=client_factory(fail),
    )

    assert external.status == "LIVE_VERIFICATION_SKIPPED_UNTRUSTED_HOST"
    assert search.status == "LIVE_VERIFICATION_SKIPPED_UNTRUSTED_HOST"
    assert external.attempted is False
    assert search.attempted is False


def test_pdf_is_reported_as_unsupported_without_retaining_text():
    result = verify_live_source(
        "https://www.elitigation.sg/Documents/judgment.pdf",
        {"canonical_name": "Lim v Tan"},
        client_factory=client_factory(
            lambda request: httpx.Response(
                200,
                headers={"content-type": "application/pdf"},
                content=b"%PDF-1.7",
            )
        ),
    )

    assert result.status == "LIVE_UNSUPPORTED_FORMAT"
    assert result.source_verified is False


def test_http_error_is_reported_without_retrying():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        raise httpx.ConnectError("connection refused", request=request)

    result = verify_live_source(
        "https://www.elitigation.sg/gdviewer/s/2023_SGCA_12",
        {"canonical_name": "Lim v Tan"},
        client_factory=client_factory(handler),
    )

    assert result.status == "LIVE_SOURCE_UNAVAILABLE"
    assert result.attempted is True
    assert len(requests) == 1
    assert "Lauudit-Verifier/" in requests[0].headers["user-agent"]


def test_redirect_outside_allowlist_is_not_followed():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            302,
            headers={"location": "https://example.com/private"},
        )

    result = verify_live_source(
        "https://www.elitigation.sg/gdviewer/s/2023_SGCA_12",
        {"canonical_name": "Lim v Tan"},
        client_factory=client_factory(handler),
    )

    assert result.status == "LIVE_SOURCE_UNAVAILABLE"
    assert result.source_verified is False
    assert result.final_url == "https://example.com/private"
    assert len(requests) == 1


@pytest.mark.live
@pytest.mark.skipif(
    os.getenv("RUN_LIVE_TESTS") != "1",
    reason="Set RUN_LIVE_TESTS=1 after confirming the source is permitted and reachable.",
)
def test_live_elitigation_smoke():
    """Opt-in smoke test; this is the sole real-network test in the suite."""
    case_name = os.getenv("LIVE_CASE_NAME")
    if not case_name:
        pytest.fail("Set LIVE_CASE_NAME to the exact visible case name before running live tests.")

    result = verify_live_source(
        os.getenv(
            "LIVE_SOURCE_URL",
            "https://www.elitigation.sg/gdviewer/s/2026_SGCA_39",
        ),
        {
            "canonical_name": case_name,
            "neutral_citation": os.getenv("LIVE_NEUTRAL_CITATION", "[2026] SGCA 39"),
            "decision_date": os.getenv("LIVE_DECISION_DATE"),
        },
    )

    assert result.attempted is True
    assert result.status == "LIVE_VERIFIED", result.reason
