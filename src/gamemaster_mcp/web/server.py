"""The web server, run inside the MCP server's process for as long as it runs.

roomkit-ui starts the MCP server and stops it; the pages come and go with it
(browsers reconnect by themselves). The web pages must never stop the game:
a taken port only logs a warning, and uvicorn leaves signals and logging to
the MCP server.
"""

import asyncio
import contextlib
import ipaddress
import logging
import socket
from collections.abc import AsyncIterator, Iterator

import uvicorn
from starlette.types import ASGIApp

from gamemaster_mcp.config import WebSettings
from gamemaster_mcp.game.dice import DiceLog
from gamemaster_mcp.storage import CampaignStore
from gamemaster_mcp.web.access import PlayerLinks, lan_address
from gamemaster_mcp.web.audiences import Sources
from gamemaster_mcp.web.changes import Changes
from gamemaster_mcp.web.routes import create_app

logger = logging.getLogger(__name__)

STOP_SECONDS = 5.0


@contextlib.asynccontextmanager
async def web_pages(
    settings: WebSettings | None, store: CampaignStore, dice: DiceLog, changes: Changes
) -> AsyncIterator[None]:
    """Serve the pages while the context is open; nothing when *settings* is None."""
    if settings is None:
        yield
        return
    links = PlayerLinks.open(store.data_dir)
    app = create_app(Sources(store, dice, changes, links, settings))
    async with serving(app, settings):
        try:
            yield
        finally:
            changes.close()  # ends the open feeds, so the server stops at once


@contextlib.asynccontextmanager
async def serving(app: ASGIApp, settings: WebSettings) -> AsyncIterator[str | None]:
    """Run *app* on the configured port; yields its address, or None if it is taken."""
    try:
        sock = _listen(settings.host, settings.port)
    except OSError as exc:
        logger.warning(
            "Web pages are off: cannot listen on %s port %s (%s).",
            settings.host,
            settings.port,
            exc.strerror or exc,
        )
        yield None
        return
    config = uvicorn.Config(
        app,
        log_config=None,  # the MCP server's logging (stderr) stays as it is
        access_log=False,
        lifespan="off",
        ws="none",
        proxy_headers=False,  # the backstage trusts the peer address only
        server_header=False,
        timeout_graceful_shutdown=1,
    )
    server = _EmbeddedServer(config)
    task = asyncio.create_task(server.serve(sockets=[sock]))
    url = _announce(sock, settings)
    try:
        yield url
    finally:
        server.should_exit = True
        try:
            await asyncio.wait_for(task, STOP_SECONDS)
        except TimeoutError:
            task.cancel()


class _EmbeddedServer(uvicorn.Server):
    """A uvicorn server that leaves Ctrl-C and SIGTERM to the MCP server around it."""

    @contextlib.contextmanager
    def capture_signals(self) -> Iterator[None]:
        yield


def _listen(host: str, port: int) -> socket.socket:
    # Bound here rather than by uvicorn, which exits the process on failure.
    family, kind, proto, _, address = socket.getaddrinfo(
        host or None, port, type=socket.SOCK_STREAM, flags=socket.AI_PASSIVE
    )[0]
    sock = socket.socket(family, kind, proto)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(address)
        sock.listen(64)
        sock.setblocking(False)
    except OSError:
        sock.close()
        raise
    return sock


def _announce(sock: socket.socket, settings: WebSettings) -> str:
    host, port = sock.getsockname()[:2]
    everywhere = ipaddress.ip_address(host).is_unspecified
    local = f"http://127.0.0.1:{port}" if everywhere else _url(host, port)
    logger.info("Table screen: %s/table/  Backstage: %s/gm/", local, local)
    lan = lan_address() if everywhere else None
    phones = settings.public_url or (_url(lan, port) if lan else None)
    if phones:
        logger.info("Phones on this network: %s/table/", phones)
    return local


def _url(host: str, port: int) -> str:
    return f"http://[{host}]:{port}" if ":" in host else f"http://{host}:{port}"
