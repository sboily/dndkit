"""Change notices: tools change the game in worker threads, web feeds wait on a loop."""

import asyncio
import contextlib
import threading

Waiter = tuple[asyncio.AbstractEventLoop, asyncio.Event]


class Changes:
    """A version that goes up at every change to the game, and wakes whoever waits.

    The campaign store and the dice log call ``notify`` from FastMCP's worker
    threads; web feeds ``await wait(...)`` on an event loop. ``close`` wakes
    everyone for good, so open feeds end when the server stops.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._version = 0
        self._closed = False
        self._waiters: set[Waiter] = set()

    @property
    def version(self) -> int:
        """How many changes so far."""
        with self._lock:
            return self._version

    @property
    def closed(self) -> bool:
        """True once the server stops: feeds should end."""
        with self._lock:
            return self._closed

    def notify(self) -> None:
        """Something changed: wake every waiting feed. Safe from any thread."""
        with self._lock:
            self._version += 1
            waiters = list(self._waiters)
        _wake(waiters)

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
            if self._version != seen or self._closed:
                return self._version
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
