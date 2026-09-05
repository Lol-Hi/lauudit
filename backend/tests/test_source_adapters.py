import httpx

from backend.app.verifiers.live_source import verify_live_source


def client_factory(handler):
    transport = httpx.MockTransport(handler)

    def factory(**kwargs):
        return httpx.Client(transport=transport, **kwargs)

    return factory


def test_judiciary_adapter_extracts_common_metadata():
    html = """
    <html><head>
      <title>Lim v Tan [2023] SGCA 12 | Singapore Courts</title>
      <meta name="citation_title" content="Lim v Tan [2023] SGCA 12">
      <meta name="citation_date" content="2023-01-01">
    </head><body>
      <main><h1 class="case-title">Lim v Tan [2023] SGCA 12</h1>
      <p>Court of Appeal</p></main>
    </body></html>
    """
    result = verify_live_source(
        "https://www.judiciary.gov.sg/judgments/lim-v-tan",
        {
            "canonical_name": "Lim v Tan",
            "neutral_citation": "[2023] SGCA 12",
            "court": "Court of Appeal",
            "decision_date": "2023-01-01",
        },
        client_factory=client_factory(
            lambda request: httpx.Response(200, headers={"content-type": "text/html"}, text=html)
        ),
    )

    assert result.status == "LIVE_VERIFIED"
    assert result.metadata_match == {"name": True, "citation": True, "court": True, "date": True}


def test_singapore_law_watch_adapter_extracts_article_metadata():
    html = """
    <html><head>
      <title>Lim v Tan [2023] SGCA 12 - Singapore Law Watch</title>
      <meta property="og:title" content="Lim v Tan [2023] SGCA 12">
    </head><body>
      <article>
        <div class="entry-title">Lim v Tan [2023] SGCA 12</div>
        <time datetime="2023-01-01">1 January 2023</time>
      </article>
    </body></html>
    """
    result = verify_live_source(
        "https://www.singaporelawwatch.sg/judgments/lim-v-tan",
        {
            "canonical_name": "Lim v Tan",
            "neutral_citation": "[2023] SGCA 12",
            "court_code": "SGCA",
            "decision_date": "2023-01-01",
        },
        client_factory=client_factory(
            lambda request: httpx.Response(200, headers={"content-type": "text/html"}, text=html)
        ),
    )

    assert result.status == "LIVE_VERIFIED"
    assert result.case_name == "Lim v Tan"
    assert result.decision_date == "2023-01-01"
    assert result.metadata_match == {"name": True, "citation": True, "court_code": True, "date": True}
