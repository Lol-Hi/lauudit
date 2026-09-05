from backend.app.normalization.case_names import name_matches_canonical, normalize_case_name


def test_normalization_handles_v_pp_and_ampersand():
    assert normalize_case_name("PP v. Tan & Co") == "PUBLIC PROSECUTOR V TAN AND CO"
    assert name_matches_canonical("Tan v. Lim", "Lim versus Tan") is False
    assert name_matches_canonical("Lim v Tan", "Lim v Tan") is True

