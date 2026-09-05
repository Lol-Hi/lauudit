import httpx

from backend.app.verifiers.source_search import search_elitigation


SEARCH_HTML = """
<div class="gd-card-body">
  <a class="h5 gd-heardertext" href="/gdviewer/s/2014_SGCA_28">Ting Siew May v Boon Lay Choo and another</a>
  <a class="citation-num-link" href="#"><span>[2014] SGCA 28 |</span></a>
  <a class="decision-date-link" href="#"><span>Decision Date: 26 May 2014 |</span></a>
</div>
"""


def test_search_extracts_direct_judgment_candidate_and_uses_exact_citation():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, headers={"content-type": "text/html"}, text=SEARCH_HTML)

    transport = httpx.MockTransport(handler)
    result = search_elitigation(
        "Ting Siew May v Boon Lay Choo and another",
        "[2014] SGCA 28",
        client_factory=lambda **kwargs: httpx.Client(transport=transport, **kwargs),
    )

    assert result.attempted is True
    assert result.query == '"[2014] SGCA 28"'
    assert len(result.candidates) == 1
    assert result.candidates[0].url == "https://www.elitigation.sg/gdviewer/s/2014_SGCA_28"
    assert requests[0].url.params["SearchPhrase"] == '"[2014] SGCA 28"'


def test_search_does_not_make_a_request_without_a_citation_or_name():
    result = search_elitigation(None, None, client_factory=lambda **kwargs: (_ for _ in ()).throw(AssertionError()))

    assert result.attempted is False
    assert result.candidates == []
