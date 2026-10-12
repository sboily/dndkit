"""Change notices: tools change the game in worker threads, web feeds wait on a loop."""

import asyncio
import contextlib
import threading

Waiter = tuple[asyncio.AbstractEventLoop, asyncio.Event]

GAME = "game"  # the campaign and the dice: what every page shows
ACTIVITY = "activity"  # the model's calls, read ones included: the backstage's log only


class Changes:
    """Versions that go up at every change, one per topic, and wake whoever waits.

    The campaign store and the dice log call ``notify`` from FastMCP's worker
    threads, the activity log ``notify_activity``; web feeds ``await wait(...)``
    on an event loop. A view follows one topic, so a read-only call refreshes
    the backstage's log and nothing else. ``close`` wakes everyone for good, so
    open feeds end when the server stops.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._versions = {GAME: 0, ACTIVITY: 0}
        self._closed = False
        self._waiters: set[Waiter] = set()

    @property
    def version(self) -> int:
        """How many changes so far, all topics."""
        with self._lock:
            return sum(self._versions.values())

    def versions(self) -> dict[str, int]:
        """How many changes so far, by topic."""
        with self._lock:
            return dict(self._versions)

    @property
    def closed(self) -> bool:
        """True once the server stops: feeds should end."""
        with self._lock:
            return self._closed

    def notify(self, topic: str = GAME) -> None:
        """Something changed: wake every waiting feed. Safe from any thread."""
        with self._lock:
            self._versions[topic] += 1
            waiters = list(self._waiters)
        _wake(waiters)

    def notify_activity(self) -> None:
        """The model called something: only the activity log changed."""
        self.notify(ACTIVITY)

    def close(self) -> None:
        """Wake every feed, which then ends."""
        with self._lock:
            self._closed = True
            waiters = list(self._waiters)
        _wake(waiters)

    async def wait(self, seen: int, timeout: float) -> int:
        """The version once it is no longer *seen*, or after *timeout* seconds anyway."""
        waiter = (asyncio.get_running_loop(), asyncio.Event())
        with self._lock:
            if sum(self._versions.values()) != seen or self._closed:
                return sum(self._versions.values())
            self._waiters.add(waiter)
        try:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(waiter[1].wait(), timeout)
        finally:
            with self._lock:
                self._waiters.discard(waiter)
        return self.version


def _wake(waiters: list[Waiter]) -> None:
    for loop, event in waiters:
        # A loop already closed has nobody left to wake.
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(event.set)
