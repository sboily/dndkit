"""What the model asks of the server, kept for the game master's backstage.

Every tool call is recorded with its arguments, its answer or its error and
how long it took, and so are the skills the client fetches: enough to follow
what the model does, and to see why something did not happen. The log lives
in memory for the session, like the dice log; nothing is saved. Calls a client
refuses before sending them never reach the server, so they are not here.
"""

import itertools
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

TEXT_LIMIT = 1200  # characters kept of arguments and answers


@dataclass(frozen=True)
class Call:
    """One request from the model."""

    number: int
    at: float  # unix time
    kind: str  # "tool" or "skill"
    name: str
    arguments: str
    outcome: str
    failed: bool
    milliseconds: int


class ActivityLog:
    """The latest calls, safe from FastMCP's worker threads."""

    def __init__(self, size: int = 200) -> None:
        self._calls: deque[Call] = deque(maxlen=size)
        self._counter = itertools.count(1)
        self._lock = threading.Lock()
        self.on_record: Callable[[], None] = lambda: None  # set by the server's lifespan

    def record(
        self, kind: str, name: str, arguments: str, outcome: str, failed: bool, started: float
    ) -> None:
        """Keep one call; *started* is its ``time.perf_counter()`` start."""
        call = Call(
            number=next(self._counter),
            at=time.time(),
            kind=kind,
            name=name,
            arguments=_cut(arguments),
            outcome=_cut(outcome),
            failed=failed,
            milliseconds=round((time.perf_counter() - started) * 1000),
        )
        with self._lock:
            self._calls.append(call)
        self.on_record()

    def recent(self) -> list[Call]:
        """Oldest first."""
        with self._lock:
            return list(self._calls)


def _cut(text: str) -> str:
    return text if len(text) <= TEXT_LIMIT else text[: TEXT_LIMIT - 1] + "…"
