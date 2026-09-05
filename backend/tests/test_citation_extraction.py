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


def test_extracts_long_and_parenthetical_reference_names():
    result = extract_citations(
        "CKR Contract Services Pte Ltd v Asplenium Land Pte Ltd and another and another appeal and another matter [2015] SGCA 24\n"
        "Star City Pty Ltd (formerly known as Sydney Harbour Casino Pty Ltd) v Tan Hong Woon [2002] SGCA 10"
    )

    assert result[0].provided_name == "CKR Contract Services Pte Ltd v Asplenium Land Pte Ltd and another and another appeal and another matter"
    assert result[1].provided_name == "Star City Pty Ltd (formerly known as Sydney Harbour Casino Pty Ltd) v Tan Hong Woon"


def test_groups_parallel_citations():
    result = extract_citations(
        "Lim v Tan [2023] SGCA 12; [2023] 2 SLR 100 held a rule."
    )

    assert len(result) == 1
    assert result[0].provided_citation == "[2023] SGCA 12"
    assert result[0].parallel_citations == ["[2023] SGCA 12", "[2023] 2 SLR 100"]


def test_does_not_group_citations_from_separate_reference_lines():
    result = extract_citations(
        "Ting Siew May v Boon Lay Choo and another [2014] SGCA 28\n"
        "Shell Eastern Petroleum (Pte) Ltd v Chuan Hong Auto (Pte) Ltd [1995] SGHC 114"
    )

    assert [item.provided_name for item in result] == [
        "Ting Siew May v Boon Lay Choo and another",
        "Shell Eastern Petroleum (Pte) Ltd v Chuan Hong Auto (Pte) Ltd",
    ]
    assert [item.provided_citation for item in result] == ["[2014] SGCA 28", "[1995] SGHC 114"]
    assert all(not item.parallel_citations for item in result)


def test_marks_numbered_footnote_context():
    result = extract_citations("See footnote 1.\n\n1. Lim v Tan [2023] SGCA 12.")

    assert len(result) == 1
    assert result[0].context_type == "footnote"
    assert result[0].footnote_number == "1"
