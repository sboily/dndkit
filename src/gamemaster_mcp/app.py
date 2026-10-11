"""Server assembly and the command-line entry point.

Nothing touches the disk at import: the campaign store opens in the server's
lifespan, so importing the package (tests, ``fastmcp inspect``) has no side
effect, and a bad data directory fails the start with one clear log line.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from gamemaster_mcp import __version__
from gamemaster_mcp.config import configure_logging, resolve_data_dir
from gamemaster_mcp.game.dice import DiceLog
from gamemaster_mcp.storage import CampaignStore
from gamemaster_mcp.tools import ALL_TOOLS
from gamemaster_mcp.tools.apps import register_apps
from gamemaster_mcp.tools.deps import DICE_LOG_KEY, STORE_KEY
from gamemaster_mcp.tools.schema import compact

logger = logging.getLogger(__name__)

INSTRUCTIONS = """\
Campaign manager for a Dungeons & Dragons 5e game master, built for voice play.
One campaign is active at a time; list_campaigns and load_campaign switch it.
Characters, NPCs, locations and quests are found by name (case and accents do
not matter) or by ID. A failed call says why and lists the known names: retry
with one of them rather than inventing a new entity. Use change_hit_points for
damage and healing (characters and monsters alike), roll_dice for every roll,
and log notable moments with add_event."""


def build_server(data_dir: Path | None = None) -> FastMCP:
    """The MCP server; campaigns live in *data_dir*, else the configured directory."""

    @asynccontextmanager
    async def lifespan(_server: FastMCP) -> AsyncIterator[dict[str, Any]]:
        directory = data_dir or resolve_data_dir()
        logger.info("Gamemaster MCP %s, data in %s", __version__, directory)
        yield {STORE_KEY: CampaignStore(directory), DICE_LOG_KEY: DiceLog()}

    server = FastMCP(
        name="gamemaster-mcp",
        instructions=INSTRUCTIONS,
        version=__version__,
        lifespan=lifespan,
        # Unexpected exceptions reach the client as a bare failure; game
        # errors (``GameError``) keep their message, written for the model.
        mask_error_details=True,
    )
    for fn in ALL_TOOLS:
        tool = server.add_tool(fn)
        tool.parameters = compact(tool.parameters)
    register_apps(server)
    return server


def main() -> None:
    """Run the server over stdio, the transport MCP clients launch."""
    configure_logging()
    build_server().run(show_banner=False)
