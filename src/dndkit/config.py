"""Runtime configuration: where the data lives, how much is logged, the web pages,
and how clients reach the server (stdio, or HTTP for a server of its own).

MCP clients such as roomkit-ui or Claude Desktop start the server with no
working directory of their own (often ``/`` on macOS), so the data directory
never depends on the current directory: it comes from the environment, else
the platform's per-user data directory.

The project was called gamemaster-mcp before its rename: its ``GAMEMASTER_*``
variables and its data directory still work.
"""

import ipaddress
import logging
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_data_path

APP_NAME = "dndkit"
LEGACY_NAME = "gamemaster-mcp"
ENV_PREFIX, LEGACY_ENV_PREFIX = "DNDKIT_", "GAMEMASTER_"
ENV_DATA_DIR = "DNDKIT_STORAGE_DIR"
ENV_LOG_LEVEL = "DNDKIT_LOG_LEVEL"
ENV_WEB_PORT = "DNDKIT_WEB_PORT"
ENV_WEB_HOST = "DNDKIT_WEB_HOST"
ENV_WEB_URL = "DNDKIT_WEB_URL"
ENV_TRANSPORT = "DNDKIT_TRANSPORT"
ENV_HTTP_HOST = "DNDKIT_HTTP_HOST"
ENV_HTTP_PORT = "DNDKIT_HTTP_PORT"
# Names and advice, not secrets: bandit takes any "token" string for a password.
ENV_HTTP_TOKEN = "DNDKIT_HTTP_TOKEN"  # nosec B105
DEFAULT_WEB_HOST = "127.0.0.1"
DEFAULT_HTTP_PORT = 8000
MIN_TOKEN_LENGTH = 16
MAKE_A_TOKEN = "openssl rand -hex 32"  # nosec B105

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WebSettings:
    """Where the web pages listen. Port 0 picks a free one (tests)."""

    port: int
    host: str = DEFAULT_WEB_HOST
    public_url: str | None = None  # how phones reach the pages when the server cannot tell


@dataclass(frozen=True)
class HttpSettings:
    """Where the MCP server listens over HTTP, and the token each request must carry."""

    host: str = DEFAULT_WEB_HOST
    port: int = DEFAULT_HTTP_PORT
    token: str | None = None


class SettingsError(ValueError):
    """A setting the server cannot start with."""


def setting(env: Mapping[str, str], name: str) -> str:
    """``$name``, else the same variable under its name from before the rename."""
    value = env.get(name, "").strip()
    if not value and name.startswith(ENV_PREFIX):
        value = env.get(LEGACY_ENV_PREFIX + name.removeprefix(ENV_PREFIX), "").strip()
    return value


def resolve_data_dir(env: Mapping[str, str] = os.environ) -> Path:
    """The data directory: ``$DNDKIT_STORAGE_DIR``, else the per-user data dir.

    A relative path would depend on the client's working directory: it is
    refused, and the per-user data dir used instead.
    """
    configured = setting(env, ENV_DATA_DIR)
    if configured:
        path = Path(configured).expanduser()
        if path.is_absolute():
            return path.resolve()
        logger.warning("Ignoring %s=%r: give an absolute path.", ENV_DATA_DIR, configured)
    return per_user_data_dir(
        user_data_path(APP_NAME, appauthor=False), user_data_path(LEGACY_NAME, appauthor=False)
    )


def per_user_data_dir(current: Path, legacy: Path) -> Path:
    """*current*, unless only the data directory from before the rename exists."""
    if not current.exists() and legacy.is_dir():
        return legacy
    return current


def configure_logging(env: Mapping[str, str] = os.environ) -> None:
    """Log to stderr: on the stdio transport, stdout carries the MCP protocol."""
    name = (setting(env, ENV_LOG_LEVEL) or "INFO").upper()
    # A misspelt level falls back to INFO: a typo must not stop the server.
    level = logging.getLevelNamesMapping().get(name, logging.INFO)
    logging.basicConfig(
        level=level,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def resolve_web_settings(env: Mapping[str, str] = os.environ) -> WebSettings | None:
    """The web pages' settings; None (no web pages) unless ``$DNDKIT_WEB_PORT`` is set."""
    raw_port = setting(env, ENV_WEB_PORT)
    if not raw_port:
        return None
    port = _port(raw_port)
    if port is None:
        # The game must still run: only the web pages are lost to a typo.
        logger.warning("Web pages are off: %s=%r is not a port number.", ENV_WEB_PORT, raw_port)
        return None
    public_url = setting(env, ENV_WEB_URL).rstrip("/") or None
    if public_url and not public_url.startswith(("http://", "https://")):
        logger.warning("Ignoring %s=%r: not an http(s) address.", ENV_WEB_URL, public_url)
        public_url = None
    return WebSettings(
        port=port,
        host=setting(env, ENV_WEB_HOST) or DEFAULT_WEB_HOST,
        public_url=public_url,
    )


def resolve_http_settings(env: Mapping[str, str] = os.environ) -> HttpSettings | None:
    """None for stdio, the default; how to listen for ``DNDKIT_TRANSPORT=http``.

    Unlike the web pages', a bad value stops the start: without its endpoint
    there is no game. Listening beyond this machine takes a token.
    """
    transport = (setting(env, ENV_TRANSPORT) or "stdio").lower()
    if transport == "stdio":
        return None
    if transport != "http":
        raise SettingsError(f"{ENV_TRANSPORT} is stdio or http, not {transport!r}.")
    raw_port = setting(env, ENV_HTTP_PORT) or str(DEFAULT_HTTP_PORT)
    port = _port(raw_port)
    if port is None:
        raise SettingsError(f"{ENV_HTTP_PORT}={raw_port!r} is not a port number.")
    host = setting(env, ENV_HTTP_HOST) or DEFAULT_WEB_HOST
    token = setting(env, ENV_HTTP_TOKEN) or None
    if token is not None and len(token) < MIN_TOKEN_LENGTH:
        raise SettingsError(
            f"{ENV_HTTP_TOKEN} needs {MIN_TOKEN_LENGTH} characters at least ({MAKE_A_TOKEN})."
        )
    if token is None and not _is_loopback(host):
        raise SettingsError(
            f"Listening on {host} lets other computers in: set {ENV_HTTP_TOKEN} "
            f"({MAKE_A_TOKEN}), or {ENV_HTTP_HOST}=127.0.0.1."
        )
    return HttpSettings(host, port, token)


def _port(raw: str) -> int | None:
    if not (raw.isascii() and raw.isdigit()) or int(raw) > 65535:
        return None
    return int(raw)


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False
