from backend.app.verifiers.url_classifier import classify_url


def test_known_corpus_url_is_normalized():
    result = classify_url(
        "HTTPS://Official.Test/case-1/#paragraph-42",
        ["https://official.test/case-1"],
    )
    assert result.status == "KNOWN_CORPUS_SOURCE"
    assert result.normalized_url == "https://official.test/case-1"


def test_elitigation_source_and_search_page():
    source = classify_url("https://www.elitigation.sg/Documents/judgment.pdf")
    search = classify_url("https://www.elitigation.sg/gdviewer/Home/Index?CurrentPage=1")
    assert source.status == "OFFICIAL_ELITIGATION_SOURCE"
    assert search.status == "OFFICIAL_SOURCE_SEARCH_PAGE"


def test_judiciary_source():
    result = classify_url("https://www.judiciary.gov.sg/judgments/example")
    assert result.status == "OFFICIAL_JUDICIARY_SOURCE"


def test_singapore_law_watch_publisher_and_judgments_page():
    source = classify_url("https://www.singaporelawwatch.sg/Portals/0/Docs/Judgments/2004-SGHC-171.pdf")
    search = classify_url("https://www.singaporelawwatch.sg/Judgments")
    assert source.status == "TRUSTED_PUBLISHER_SOURCE"
    assert search.status == "TRUSTED_PUBLISHER_SEARCH_PAGE"


def test_external_and_malformed_urls():
    external = classify_url("https://example.com/case/123")
    malformed = classify_url("not-a-url")
    assert external.status == "UNVERIFIED_EXTERNAL_URL"
    assert malformed.status == "MALFORMED_URL"


def test_lookalike_domain_is_not_official():
    result = classify_url("https://www.elitigation.sg.evil.example/case")
    assert result.status == "UNVERIFIED_EXTERNAL_URL"
