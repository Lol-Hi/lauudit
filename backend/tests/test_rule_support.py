from backend.app.corpus.database import connect
from backend.app.verifiers.rule_support import evaluate_rule_support


def test_rule_support_is_cautious(indexed_db):
    connection = connect(indexed_db)
    supported = evaluate_rule_support(connection, "case-1", "Lim v Tan held that contractual agreement is assessed objectively by the parties' words and conduct.")
    unsupported = evaluate_rule_support(connection, "case-1", "Lim v Tan held that every promise is automatically enforceable in every circumstance.")
    assert supported.classification == "SUPPORTED"
    assert supported.evidence[0]["paragraph"] == 42
    assert unsupported.classification in {"UNSUPPORTED", "UNCERTAIN", "UNABLE_TO_EVALUATE"}
