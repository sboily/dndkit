"""The web site: pages and their live feeds, for three audiences.

    /table/       the shared screen: public views and the players' join codes
    /p/<token>/   one player's phone: public views and that character's sheet
    /gm/          the game master's backstage, only from this machine

Each page is self-contained HTML (``ui.page``) that opens one event stream,
``feed?views=a,b``, relative to its own address. Every page is read-only:
the game changes only through the MCP tools, so the model always knows.
"""

from urllib.parse import urlsplit

import anyio.to_thread
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import (
    HTMLResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
from starlette.routing import Route

from dndkit import ui
from dndkit.config import WebSettings
from dndkit.web import audiences, feed
from dndkit.web.access import is_loopback
from dndkit.web.audiences import Sources, Views

PAGE_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",  # a player's address holds their token
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
        "img-src data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'"
    ),
}
PROXY_HEADERS = ("forwarded", "x-forwarded-for", "x-forwarded-host", "via")
FEED_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def create_app(sources: Sources) -> Starlette:
    """The site over *sources*, shared with the running MCP server."""

    async def table_feed(request: Request) -> Response:
        return _feed(request, sources, audiences.table(sources, str(request.base_url)))

    async def player_page(request: Request) -> Response:
        name = await _player(sources, request)
        return _page("player") if name else _refused(request, 404, "unknownLink")

    async def player_feed(request: Request) -> Response:
        token = request.path_params["token"]
        if not await _player(sources, request):
            return _refused(request, 404, "unknownLink")
        return _feed(request, sources, audiences.player(sources, token))

    async def gm_page(request: Request) -> Response:
        if not _local(request, sources.settings):
            return _refused(request, 403, "localOnly")
        return _page("gm")

    async def gm_feed(request: Request) -> Response:
        if not _local(request, sources.settings):
            return _refused(request, 403, "localOnly")
        return _feed(request, sources, audiences.game_master(sources, str(request.base_url)))

    return Starlette(
        routes=[
            Route("/", lambda _: RedirectResponse("/table/")),
            Route("/table/", lambda _: _page("table")),
            Route("/table/feed", table_feed),
            Route("/p/{token}/", player_page),
            Route("/p/{token}/feed", player_feed),
            Route("/gm/", gm_page),
            Route("/gm/feed", gm_feed),
        ]
    )


def _page(name: str) -> Response:
    return HTMLResponse(ui.page(name, web=True), headers=PAGE_HEADERS)


def _feed(request: Request, sources: Sources, views: Views) -> Response:
    wanted = [name for name in request.query_params.get("views", "").split(",") if name]
    unknown = [name for name in wanted if name not in views]
    if not wanted or unknown:
        known = ", ".join(sorted(views))
        return PlainTextResponse(f"Ask for views among: {known}.", status_code=400)
    stream = feed.stream(sources.changes, {name: views[name] for name in wanted}, sources.renders)
    return StreamingResponse(stream, media_type="text/event-stream", headers=FEED_HEADERS)


async def _player(sources: Sources, request: Request) -> str | None:
    token = request.path_params["token"]
    return await anyio.to_thread.run_sync(sources.player, token)


def _local(request: Request, settings: WebSettings) -> bool:
    """A request from this machine, for this server.

    The peer is a loopback address or our own. The Host must name this server
    too: a hostile page whose domain resolves to 127.0.0.1 (DNS rebinding)
    would send its own domain. Anything that went through a proxy is refused.
    """
    if request.client is None or any(h in request.headers for h in PROXY_HEADERS):
        return False
    server = (request.scope.get("server") or ("", 0))[0]
    peer = request.client.host
    host = urlsplit(f"//{request.headers.get('host', '')}").hostname or ""
    ours = {server, urlsplit(settings.public_url or "").hostname}
    return (is_loopback(peer) or peer == server) and (is_loopback(host) or host in ours)


REFUSALS = {  # English, French
    "unknownLink": (
        "This link matches no character of the active campaign.",
        "Ce lien ne correspond à aucun personnage de la campagne active.",
    ),
    "localOnly": (
        "The backstage opens only on the computer running the game.",
        "La régie ne s'ouvre que sur l'ordinateur qui fait tourner la partie.",
    ),
}


def _refused(request: Request, status: int, reason: str) -> Response:
    french = request.headers.get("accept-language", "").lower().startswith("fr")
    text = REFUSALS[reason][1 if french else 0]
    return PlainTextResponse(text, status_code=status, headers=PAGE_HEADERS)
