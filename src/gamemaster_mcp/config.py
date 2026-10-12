"""Runtime configuration: where the data lives, how much is logged, the web pages.

MCP clients such as roomkit-ui or Claude Desktop start the server with no
working directory of their own (often ``/`` on macOS), so the data directory
never depends on the current directory: it comes from the environment, else
the platform's per-user data directory.
"""

import logging
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_data_path

APP_NAME = "gamemaster-mcp"
ENV_DATA_DIR = "GAMEMASTER_STORAGE_DIR"
ENV_LOG_LEVEL = "GAMEMASTER_LOG_LEVEL"
ENV_WEB_PORT = "GAMEMASTER_WEB_PORT"
ENV_WEB_HOST = "GAMEMASTER_WEB_HOST"
ENV_WEB_URL = "GAMEMASTER_WEB_URL"
DEFAULT_WEB_HOST = "127.0.0.1"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WebSettings:
    """Where the web pages listen. Port 0 picks a free one (tests)."""

    port: int
    host: str = DEFAULT_WEB_HOST
    public_url: str | None = None  # how phones reach the pages when the server cannot tell


def resolve_data_dir(env: Mapping[str, str] = os.environ) -> Path:
    """The data directory: ``$GAMEMASTER_STORAGE_DIR``, else the per-user data dir."""
    configured = env.get(ENV_DATA_DIR, "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return user_data_path(APP_NAME, appauthor=False)


def configure_logging(env: Mapping[str, str] = os.environ) -> None:
    """Log to stderr: on the stdio transport, stdout carries the MCP protocol."""
    name = env.get(ENV_LOG_LEVEL, "INFO").strip().upper()
    # A misspelt level falls back to INFO: a typo must not stop the server.
    level = logging.getLevelNamesMapping().get(name, logging.INFO)
    logging.basicConfig(
        level=level,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def resolve_web_settings(env: Mapping[str, str] = os.environ) -> WebSettings | None:
    """The web pages' settings; None (no web pages) unless ``$GAMEMASTER_WEB_PORT`` is set."""
    raw_port = env.get(ENV_WEB_PORT, "").strip()
    if not raw_port:
        return None
    if not (raw_port.isascii() and raw_port.isdigit()) or int(raw_port) > 65535:
        # The game must still run: only the web pages are lost to a typo.
        logger.warning("Web pages are off: %s=%r is not a port number.", ENV_WEB_PORT, raw_port)
        return None
    public_url = env.get(ENV_WEB_URL, "").strip().rstrip("/") or None
    if public_url and not public_url.startswith(("http://", "https://")):
        logger.warning("Ignoring %s=%r: not an http(s) address.", ENV_WEB_URL, public_url)
        public_url = None
    return WebSettings(
        port=int(raw_port),
        host=env.get(ENV_WEB_HOST, "").strip() or DEFAULT_WEB_HOST,
        public_url=public_url,
    )
