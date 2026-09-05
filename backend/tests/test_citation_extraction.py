from backend.app.extractors.citations import extract_citations


def test_extracts_neutral_reported_and_name_only_citations():
    result = extract_citations(
        "Lim v Tan [2023] SGCA 12 held a rule. Public Prosecutor v Tan Ah Kow [2023] SGHC(A) 4 was discussed. Tan v Lim was also mentioned."
    )
    assert [item.provided_citation for item in result] == ["[2023] SGCA 12", "[2023] SGHC(A) 4", None]
    assert result[0].provided_name == "Lim v Tan"
    assert result[2].provided_name == "Tan v Lim"


def test_extracts_all_requested_neutral_formats():
    result = extract_citations("[2023] SGCA 12 [2023] SGHC 55 [2023] SGDC 20 [2023] SGMC 8 [2023] 2 SLR 100")
    assert len(result) == 5


def test_extracts_party_suffixes_and_company_names():
    result = extract_citations(
        "ACME Holdings (S) Pte Ltd and another v Public Prosecutor [2023] SGHC 55 held a rule."
    )

    assert len(result) == 1
    assert result[0].provided_citation == "[2023] SGHC 55"
    assert result[0].provided_name == "ACME Holdings (S) Pte Ltd and another v Public Prosecutor"


def test_groups_parallel_citations():
    result = extract_citations(
        "Lim v Tan [2023] SGCA 12; [2023] 2 SLR 100 held a rule."
    )

    assert len(result) == 1
    assert result[0].provided_citation == "[2023] SGCA 12"
    assert result[0].parallel_citations == ["[2023] SGCA 12", "[2023] 2 SLR 100"]


def test_marks_numbered_footnote_context():
    result = extract_citations("See footnote 1.\n\n1. Lim v Tan [2023] SGCA 12.")

    assert len(result) == 1
    assert result[0].context_type == "footnote"
    assert result[0].footnote_number == "1"
