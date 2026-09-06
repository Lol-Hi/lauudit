from dataclasses import replace
from threading import Lock
import time

from backend.app import pipeline
from backend.app.schemas import AuditRequest


def test_live_verification_resolves_citations_in_parallel(monkeypatch):
    monkeypatch.setattr(
        pipeline,
        "settings",
        replace(pipeline.settings, enable_live_verification=True),
    )
    state = {"active": 0, "max_active": 0}
    state_lock = Lock()

    def resolve(citation, href, url_result, *, enabled):
        with state_lock:
            state["active"] += 1
            state["max_active"] = max(state["max_active"], state["active"])
        time.sleep(0.05)
        with state_lock:
            state["active"] -= 1
        return None, None, None

    monkeypatch.setattr(pipeline, "_resolve_elitigation", resolve)
    response = pipeline.run_audit(AuditRequest(
        response_text=(
            "Lim v Tan [2023] SGCA 12 held that agreement is assessed objectively. "
            "Foo v Bar [2022] SGHC 1 held that notice must be reasonable."
        ),
    ))

    assert response.summary.total_citations == 2
    assert state["max_active"] >= 2
