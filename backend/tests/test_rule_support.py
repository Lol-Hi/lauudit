from backend.app.corpus.database import connect
from backend.app.verifiers.rule_support import evaluate_rule_support


def test_rule_support_is_cautious(indexed_db):
    connection = connect(indexed_db)
    supported = evaluate_rule_support(connection, "case-1", "Lim v Tan held that contractual agreement is assessed objectively by the parties' words and conduct.")
    unsupported = evaluate_rule_support(connection, "case-1", "Lim v Tan held that every oral agreement is automatically valid.")
    assert supported.classification == "SUPPORTED"
    assert supported.evidence[0]["paragraph"] == 42
    assert supported.needs_human_review is False
    assert supported.confidence >= 0.7
    assert unsupported.classification in {"UNSUPPORTED", "UNCERTAIN"}
    assert unsupported.needs_human_review is True


def test_rule_support_returns_uncertain_for_partial_retrieval(indexed_db):
    connection = connect(indexed_db)
    result = evaluate_rule_support(
        connection,
        "case-1",
        "Lim v Tan held that agreement may be enforceable.",
    )

    assert result.classification == "UNCERTAIN"
    assert 0.0 < result.confidence < 0.7
    assert result.evidence
    assert result.needs_human_review is True


def test_rule_support_declines_non_rule_sentence(indexed_db):
    connection = connect(indexed_db)
    result = evaluate_rule_support(connection, "case-1", "Lim v Tan was mentioned in the response.")

    assert result.classification == "UNABLE_TO_EVALUATE"
    assert result.confidence == 0.0
    assert result.evidence == []
    assert result.needs_human_review is True
