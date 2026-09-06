"""A small in-process circuit breaker for live source network calls."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import RLock


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    cooldown_seconds: float = 60.0
    _failures: int = 0
    _open_until: float = 0.0
    _lock: RLock = field(default_factory=RLock, init=False, repr=False, compare=False)

    def is_open(self) -> bool:
        with self._lock:
            return time.monotonic() < self._open_until

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._open_until = 0.0

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._open_until = time.monotonic() + self.cooldown_seconds
