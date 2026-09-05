from backend.app.corpus.database import connect
from backend.app.verifiers.existence import verify_existence


def test_exact_citation_and_name_miss(indexed_db):
    connection = connect(indexed_db)
    found = verify_existence(connection, "Wrong v Tan", "[2023] SGCA 12")
    missing = verify_existence(connection, "Foo v Bar", "[2099] SGCA 1")
    assert found.status == "VERIFIED_EXISTS"
    assert found.case["canonical_name"] == "Lim v Tan"
    assert missing.status == "NOT_FOUND_IN_VERIFIED_CORPUS"

