"""The data tool the MCP Apps widgets read; the conversation never needs it."""

import json
from collections.abc import Callable
from typing import Annotated, Literal

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from pydantic import Field

from gamemaster_mcp.errors import InvalidChangeError
from gamemaster_mcp.game.dice import DiceLog
from gamemaster_mcp.storage import CampaignStore
from gamemaster_mcp.tools.deps import READ_ONLY, get_dice_log, get_store
from gamemaster_mcp.views import widgets

View = Literal["dice", "combat", "party", "character"]


@tool(annotations=READ_ONLY)
def get_screen_data(
    view: Annotated[View, Field(description="Which widget")],
    name: Annotated[str | None, Field(description="Character, for the character view")] = None,
    store: CampaignStore = Depends(get_store),
    log: DiceLog = Depends(get_dice_log),
) -> str:
    """JSON for the on-screen widgets. Never needed in conversation."""
    if view == "dice":
        data = widgets.dice(log)
    else:
        with store.reading() as campaign:
            if view == "combat":
                data = widgets.combat(campaign)
            elif view == "party":
                data = widgets.party(campaign)
            elif name:
                data = widgets.character(campaign, name)
            else:
                raise InvalidChangeError("The character view needs a name.")
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


TOOLS: list[Callable[..., str]] = [get_screen_data]
