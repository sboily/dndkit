"""Runtime configuration: where the data lives and how much is logged.

MCP clients such as roomkit-ui or Claude Desktop start the server with no
working directory of their own (often ``/`` on macOS), so the data directory
never depends on the current directory: it comes from the environment, else
the platform's per-user data directory.
"""

import logging
import os
import sys
from collections.abc import Mapping
from pathlib import Path

from platformdirs import user_data_path

APP_NAME = "gamemaster-mcp"
ENV_DATA_DIR = "GAMEMASTER_STORAGE_DIR"
ENV_LOG_LEVEL = "GAMEMASTER_LOG_LEVEL"


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
