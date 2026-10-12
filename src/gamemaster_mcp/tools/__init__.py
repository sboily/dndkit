"""MCP tools: thin adapters from tool calls to the game logic.

Each module lists its tools in ``TOOLS``; ``ALL_TOOLS`` is what the server
registers.
"""

from collections.abc import Callable

from gamemaster_mcp.tools import (
    battle,
    bestiary,
    campaign,
    characters,
    combat,
    journal,
    locations,
    npcs,
    play,
    players,
    progression,
    quests,
    resources,
    screen,
    spells,
    utility,
)

ALL_TOOLS: list[Callable[..., str]] = [
    *campaign.TOOLS,
    *characters.TOOLS,
    *resources.TOOLS,
    *spells.TOOLS,
    *progression.TOOLS,
    *npcs.TOOLS,
    *locations.TOOLS,
    *quests.TOOLS,
    *play.TOOLS,
    *players.TOOLS,
    *combat.TOOLS,
    *battle.TOOLS,
    *bestiary.TOOLS,
    *journal.TOOLS,
    *utility.TOOLS,
    *screen.TOOLS,
]

__all__ = ["ALL_TOOLS"]
