"""The MCP server over HTTP, for a server that runs on its own (Docker, a home server).

stdio stays the default: a client starts the server and talks on its pipes.
Over HTTP the server runs until stopped, serves MCP at ``/mcp`` (Streamable
HTTP) and answers ``/health``; with a token, every MCP request must carry it
(``Authorization: Bearer <token>``), compared in constant time.
"""

import hmac

from fastmcp import FastMCP
from fastmcp.server.auth import AccessToken, TokenVerifier
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

from dndkit.config import HttpSettings

PATH = "/mcp"
CLIENT = "dndkit-client"  # who a request was made for: whoever holds the token


class BearerToken(TokenVerifier):
    """Lets in the requests that carry the server's one token."""

    def __init__(self, token: str) -> None:
        super().__init__()
        self._token = token.encode()

    async def verify_token(self, token: str) -> AccessToken | None:
        if hmac.compare_digest(token.encode(), self._token):
            return AccessToken(token=token, client_id=CLIENT, scopes=[])
        return None


def add_health(server: FastMCP) -> None:
    """``GET /health``, for Docker and monitors: up, nothing more, no token needed."""

    @server.custom_route("/health", methods=["GET"])
    async def health(_request: Request) -> Response:
        return PlainTextResponse("ok")


def serve(server: FastMCP, settings: HttpSettings) -> None:
    """Run *server* over HTTP until stopped. Without a token it listens on this
    machine only, where Host and Origin are checked against DNS rebinding."""
    server.run(
        transport="http",
        host=settings.host,
        port=settings.port,
        path=PATH,
        show_banner=False,
        host_origin_protection="auto",
    )
