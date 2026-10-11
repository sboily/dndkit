"""MCP tools: thin adapters from tool calls to the game logic.

Each module lists its tools in ``TOOLS``; ``ALL_TOOLS`` is what the server
registers.
"""

from collections.abc import Callable

from gamemaster_mcp.tools import (
    campaign,
    characters,
    journal,
    locations,
    npcs,
    play,
    quests,
    resources,
    utility,
)

ALL_TOOLS: list[Callable[..., str]] = [
    *campaign.TOOLS,
    *characters.TOOLS,
    *resources.TOOLS,
    *npcs.TOOLS,
    *locations.TOOLS,
    *quests.TOOLS,
    *play.TOOLS,
    *journal.TOOLS,
    *utility.TOOLS,
]

__all__ = ["ALL_TOOLS"]
