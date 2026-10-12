"""Server-sent events: each view's JSON at once, then again whenever it changes.

Every open page streams its own views, but they render once per change for
all of them (``Renders``): ten phones showing the party cost one render, in a
small pool of threads of their own, so pages never keep the tools waiting.
"""

import json
import logging
import threading
from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import dataclass
from typing import Any

import anyio
import anyio.to_thread

from gamemaster_mcp.errors import GameError, NoActiveCampaignError
from gamemaster_mcp.web.changes import GAME, Changes

Render = Callable[[], Any]

logger = logging.getLogger(__name__)

HEARTBEAT_SECONDS = 15.0
RETRY_MILLISECONDS = 2000
RENDER_THREADS = 2  # the tools have FastMCP's pool; the pages share these


@dataclass(frozen=True)
class View:
    """A view to stream: how to render it, the key every feed showing the same
    thing shares (the table's party, one player's sheet), and the topic of
    changes it follows (``changes.GAME`` or ``changes.ACTIVITY``)."""

    render: Render
    key: str
    topic: str = GAME


class Renders:
    """Each view's latest text, rendered once per change for every feed."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._texts: dict[str, tuple[int, str]] = {}
        self._key_locks: dict[str, threading.Lock] = {}
        self._limiter: anyio.CapacityLimiter | None = None

    async def all(self, views: Mapping[str, View], versions: Mapping[str, int]) -> dict[str, str]:
        """The text of every view at *versions*, in the pages' own threads."""
        if self._limiter is None:
            self._limiter = anyio.CapacityLimiter(RENDER_THREADS)
        return await anyio.to_thread.run_sync(self._all, views, versions, limiter=self._limiter)

    def _all(self, views: Mapping[str, View], versions: Mapping[str, int]) -> dict[str, str]:
        return {name: self.text(view, versions[view.topic]) for name, view in views.items()}

    def text(self, view: View, version: int) -> str:
        """*view*'s text at *version* of its topic: kept, or rendered now."""
        with self._lock:
            key_lock = self._key_locks.setdefault(view.key, threading.Lock())
        with key_lock:  # a second feed asking at once waits for the first render
            kept = self._texts.get(view.key)
            if kept is not None and kept[0] == version:
                return kept[1]
            text = render(view)
            self._texts[view.key] = (version, text)
            return text


async def stream(
    changes: Changes, views: Mapping[str, View], renders: Renders
) -> AsyncIterator[str]:
    """SSE text for *views*: all of them, then those that changed after each change.

    A heartbeat comment keeps idle connections open; the stream ends when the
    server stops (``Changes.close``).
    """
    yield f"retry: {RETRY_MILLISECONDS}\n\n"
    sent: dict[str, str] = {}
    seen: dict[str, int] | None = None
    while not changes.closed:
        versions = changes.versions()
        if versions == seen:
            yield ": still here\n\n"
        else:
            seen = versions
            for name, text in (await renders.all(views, versions)).items():
                if sent.get(name) != text:
                    sent[name] = text
                    yield f"event: {name}\ndata: {text}\n\n"
        await changes.wait(sum(versions.values()), HEARTBEAT_SECONDS)


def render_once(views: Mapping[str, View]) -> dict[str, str]:
    """Every view's text now, without keeping it (tests, a one-off look)."""
    return {name: render(view) for name, view in views.items()}


def render(view: View) -> str:
    """One view's JSON; a view that fails sends its error alone, the others go on."""
    try:
        data = view.render()
    except NoActiveCampaignError:
        data = {"error": "noCampaign"}  # a word the pages translate
    except GameError as exc:
        data = {"error": str(exc)}
    except Exception:
        logger.exception("A web view failed")
        data = {"error": "viewFailed"}
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
