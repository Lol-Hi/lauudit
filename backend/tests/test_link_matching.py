from backend.app.corpus.database import connect
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
