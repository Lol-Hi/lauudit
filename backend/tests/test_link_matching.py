from backend.app.corpus.database import connect
from backend.app.extractors.citations import extract_citations
from backend.app.extractors.links import resolve_links
from backend.app.schemas import LinkInput
from backend.app.verifiers.link_match import verify_link
from backend.app.verifiers.existence import verify_existence


def test_link_outcomes(indexed_db):
    connection = connect(indexed_db)
    case = verify_existence(connection, None, "[2023] SGCA 12").case
    assert verify_link("https://official.test/case-1", case) == "LINK_CONFIRMS_CASE"
    assert verify_link(
        "https://official.test/case-1/#paragraph-42",
        case,
    ) == "LINK_CONFIRMS_CASE"
    assert verify_link("https://official.test/search?q=case", case) == "LINK_POINTS_TO_SEARCH_RESULTS"
    assert verify_link(
        "https://other.test/case-2",
        case,
        [{"case_id": "case-1", "source_url": "https://official.test/case-1"}, {"case_id": "case-2", "source_url": "https://other.test/case-2"}],
    ) == "LINK_RESOLVES_TO_DIFFERENT_CASE"
    assert verify_link("https://other.test/case-2", case) == "LINK_BROKEN_OR_INACCESSIBLE"
    assert verify_link(None, case) == "NO_LINK_AVAILABLE"


def test_adjacent_split_links_with_same_url_are_resolved():
    citation = extract_citations("Lim v Tan [2023] SGCA 12")[0]
    links = [
        LinkInput(text="Lim v Tan", href="https://official.test/case-1", context="Lim v Tan [2023] SGCA 12"),
        LinkInput(text="[2023] SGCA 12", href="https://official.test/case-1", context="Lim v Tan [2023] SGCA 12"),
    ]

    result = resolve_links(citation, links)

    assert result.status == "SINGLE"
    assert result.href == "https://official.test/case-1"
    assert result.hrefs == ("https://official.test/case-1",)


def test_adjacent_split_links_with_different_urls_are_ambiguous():
    citation = extract_citations("Lim v Tan [2023] SGCA 12")[0]
    links = [
        LinkInput(text="Lim v Tan", href="https://example.test/name", context="Lim v Tan [2023] SGCA 12"),
        LinkInput(text="[2023] SGCA 12", href="https://example.test/citation", context="Lim v Tan [2023] SGCA 12"),
    ]

    result = resolve_links(citation, links)

    assert result.status == "AMBIGUOUS"
    assert result.href is None
    assert result.hrefs == ("https://example.test/name", "https://example.test/citation")


def test_positional_link_metadata_resolves_the_exact_citation_occurrence():
    response_text = "Intro. Lim v Tan [2023] SGCA 12 held that the test is objective."
    citation = extract_citations(response_text)[0]
    links = [
        LinkInput(
            text="unrelated case",
            href="https://example.test/unrelated",
            context="unrelated case",
            start=0,
            end=14,
        ),
        LinkInput(
            text="Lim v Tan [2023] SGCA 12",
            href="https://official.test/case-1",
            context="different surrounding text",
            start=citation.start,
            end=citation.end,
        ),
    ]

    result = resolve_links(citation, links)

    assert result.status == "SINGLE"
    assert result.href == "https://official.test/case-1"


def test_overlapping_positional_links_are_ambiguous():
    response_text = "Lim v Tan [2023] SGCA 12"
    citation = extract_citations(response_text)[0]
    links = [
        LinkInput(text="name", href="https://example.test/name", start=citation.start, end=citation.end),
        LinkInput(text="citation", href="https://example.test/citation", start=citation.start, end=citation.end),
    ]

    result = resolve_links(citation, links)

    assert result.status == "AMBIGUOUS"
    assert result.hrefs == ("https://example.test/name", "https://example.test/citation")
