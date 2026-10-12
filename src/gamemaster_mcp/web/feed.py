"""Server-sent events: each view's JSON at once, then again whenever it changes."""

import json
import logging
from collections.abc import AsyncIterator, Callable, Mapping
from typing import Any

import anyio.to_thread

from gamemaster_mcp.errors import GameError, NoActiveCampaignError
from gamemaster_mcp.web.changes import Changes

Render = Callable[[], Any]

logger = logging.getLogger(__name__)

HEARTBEAT_SECONDS = 15.0
RETRY_MILLISECONDS = 2000


async def stream(changes: Changes, views: Mapping[str, Render]) -> AsyncIterator[str]:
    """SSE text for *views*: all of them, then those that changed after each change.

    A heartbeat comment keeps idle connections open; the stream ends when the
    server stops (``Changes.close``). Views render in a worker thread: the
    store's lock may be held by a tool for a moment.
    """
    yield f"retry: {RETRY_MILLISECONDS}\n\n"
    sent: dict[str, str] = {}
    seen: int | None = None
    while not changes.closed:
        version = changes.version
        if version == seen:
            yield ": still here\n\n"
        else:
            seen = version
            texts = await anyio.to_thread.run_sync(_render_all, views)
            for name, text in texts.items():
                if sent.get(name) != text:
                    sent[name] = text
                    yield f"event: {name}\ndata: {text}\n\n"
        await changes.wait(version, HEARTBEAT_SECONDS)


def _render_all(views: Mapping[str, Render]) -> dict[str, str]:
    return {name: _render(render) for name, render in views.items()}


def _render(render: Render) -> str:
    """One view's JSON; a view that fails sends its error alone, the others go on."""
    try:
        data = render()
    except NoActiveCampaignError:
        data = {"error": "noCampaign"}  # a word the pages translate
    except GameError as exc:
        data = {"error": str(exc)}
    except Exception:
        logger.exception("A web view failed")
        data = {"error": "viewFailed"}
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
