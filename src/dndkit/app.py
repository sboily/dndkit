"""Server assembly and the command-line entry point.

Nothing touches the disk at import: the campaign store opens in the server's
lifespan, so importing the package (tests, ``fastmcp inspect``) has no side
effect, and a bad data directory fails the start with one clear log line.
The web pages, when configured, run in the same lifespan.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from dndkit import __version__
from dndkit.activity import ActivityLog
from dndkit.config import (
    WebSettings,
    configure_logging,
    resolve_data_dir,
    resolve_web_settings,
)
from dndkit.game.dice import DiceLog
from dndkit.skills import register_skills
from dndkit.storage import CampaignStore
from dndkit.tools import ALL_TOOLS
from dndkit.tools.apps import register_apps
from dndkit.tools.deps import DICE_LOG_KEY, STORE_KEY
from dndkit.tools.recorder import Recorder
from dndkit.tools.schema import compact
from dndkit.web import Changes, web_pages

logger = logging.getLogger(__name__)

INSTRUCTIONS = """\
Campaign manager for a Dungeons & Dragons 5e game master, built for voice play.
You are the game master: you lead, and act with the tools without asking leave.
Read skill://dnd-game-master/SKILL.md first: the tools, a session's course, and
preparing a campaign by the rules; check_campaign then lists what is missing.
One campaign is active at a time; list_campaigns and load_campaign switch it.
Each spoken turn opens with the speaker's name: a player. seat_players says
who plays which character; "I attack" from a player is their character's
action. At the start of a session, ask who is at the table and call
seat_players with start_over; call it again when someone arrives or leaves.
Characters, NPCs, locations and quests are found by name (case and accents do
not matter) or by ID. A failed call says why and lists the known names: retry
with one of them rather than inventing a new entity. Use change_hit_points for
damage and healing (characters and monsters alike), roll_dice for every roll,
and log notable moments with add_event. Resolve every roll yourself: the attack
against the target's AC, then the damage, applied with change_hit_points; never
ask the players for a total or a number the tools hold (get_character gives a
character's spell attack and save DC). You run the monsters: one the story
needs and the bestiary lacks is yours to create with save_monster (a challenge
rating sets its stats; mark the boss), then plan_encounter rates the fight.
How-to skills, which also bring their tools when your client hides them:
skill://dnd-monsters/SKILL.md (save_monster, plan_encounter: monsters, bosses,
sizing a fight) and skill://dnd-battle-map/SKILL.md (the map tools)."""


def build_server(data_dir: Path | None = None, web: WebSettings | None = None) -> FastMCP:
    """The MCP server; campaigns live in *data_dir*, else the configured directory.

    With *web*, the server also serves the live web pages (``web/``).
    """

    activity = ActivityLog()  # in memory, filled by the Recorder middleware

    @asynccontextmanager
    async def lifespan(_server: FastMCP) -> AsyncIterator[dict[str, Any]]:
        directory = data_dir or resolve_data_dir()
        logger.info("dndkit %s, data in %s", __version__, directory)
        changes = Changes()
        store = CampaignStore(directory, on_change=changes.notify)
        dice_log = DiceLog(on_record=changes.notify)
        activity.on_record = changes.notify_activity
        try:
            async with web_pages(web, store, dice_log, activity, changes):
                yield {STORE_KEY: store, DICE_LOG_KEY: dice_log}
        finally:
            store.close()

    server = FastMCP(
        name="dndkit",
        instructions=INSTRUCTIONS,
        version=__version__,
        lifespan=lifespan,
        # Unexpected exceptions reach the client as a bare failure; game
        # errors (``GameError``) keep their message, written for the model.
        mask_error_details=True,
        middleware=[Recorder(activity)],
    )
    for fn in ALL_TOOLS:
        tool = server.add_tool(fn)
        tool.parameters = compact(tool.parameters)
    register_apps(server)
    register_skills(server, activity)
    return server


def main() -> None:
    """Run the server over stdio, the transport MCP clients launch."""
    configure_logging()
    build_server(web=resolve_web_settings()).run(show_banner=False)
