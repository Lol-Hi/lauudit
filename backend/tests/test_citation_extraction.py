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

