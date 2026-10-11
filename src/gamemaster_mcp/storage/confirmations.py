"""One-time codes a destructive action must be called back with.

A spoken "delete the campaign" may be misheard. The first call only issues a
code and says what would be lost; the action happens on a second call that
carries the code, which the model makes after the players say yes. A code
serves once, for one target, and expires; a wrong code cancels the request.
"""

import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

CODE_TTL_SECONDS = 300.0


@dataclass(frozen=True)
class _Pending:
    code: str
    expires_at: float


class Confirmations:
    """Pending confirmation codes, one per target."""

    def __init__(
        self, ttl: float = CODE_TTL_SECONDS, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._ttl = ttl
        self._clock = clock
        self._pending: dict[str, _Pending] = {}
        self._lock = threading.Lock()

    @property
    def ttl_minutes(self) -> int:
        """The lifetime of a code, in whole minutes, for messages."""
        return max(1, round(self._ttl / 60))

    def issue(self, target: str) -> str:
        """A fresh 4-digit code for *target*; it replaces any earlier one."""
        code = f"{secrets.randbelow(10_000):04d}"
        with self._lock:
            self._pending[target] = _Pending(code=code, expires_at=self._clock() + self._ttl)
        return code

    def consume(self, target: str, code: str) -> bool:
        """Whether *code* confirms *target*. Either way the pending code is spent."""
        with self._lock:
            pending = self._pending.pop(target, None)
        if pending is None or self._clock() > pending.expires_at:
            return False
        return secrets.compare_digest(pending.code, code.strip())
