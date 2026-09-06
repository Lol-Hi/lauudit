from backend.app.verifiers.circuit_breaker import CircuitBreaker


def test_circuit_breaker_opens_after_threshold_and_closes_after_cooldown(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("backend.app.verifiers.circuit_breaker.time.monotonic", lambda: clock[0])
    breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=60.0)

    breaker.record_failure()
    breaker.record_failure()
    assert breaker.is_open() is False

    breaker.record_failure()
    assert breaker.is_open() is True

    clock[0] = 160.0
    assert breaker.is_open() is False


def test_circuit_breaker_success_resets_failure_count(monkeypatch):
    monkeypatch.setattr("backend.app.verifiers.circuit_breaker.time.monotonic", lambda: 100.0)
    breaker = CircuitBreaker(failure_threshold=2, cooldown_seconds=60.0)

    breaker.record_failure()
    breaker.record_success()
    breaker.record_failure()

    assert breaker.is_open() is False
