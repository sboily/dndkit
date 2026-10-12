"""The data tool the MCP Apps widgets read; the conversation never needs it."""

import json
from collections.abc import Callable
from typing import Annotated, Literal

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from pydantic import Field

from dndkit.errors import InvalidChangeError
from dndkit.game.dice import DiceLog
from dndkit.models import Campaign
from dndkit.storage import CampaignStore
from dndkit.tools.deps import READ_ONLY, JoinCodes, get_dice_log, get_join_codes, get_store
from dndkit.views import everyone, widgets

View = Literal["dice", "combat", "party", "character", "seating", "join"]
WEB_OFF: everyone.Json = {"off": True, "reachable": False, "players": []}
CAMPAIGN_VIEWS: dict[str, Callable[[Campaign], everyone.Json]] = {
    "combat": widgets.combat,
    "party": everyone.party,
    "seating": everyone.seating_chart,
}


@tool(annotations=READ_ONLY)
def get_screen_data(
    view: Annotated[View, Field(description="Which widget")],
    name: Annotated[str | None, Field(description="Character, for the character view")] = None,
    store: CampaignStore = Depends(get_store),
    log: DiceLog = Depends(get_dice_log),
    codes: JoinCodes | None = Depends(get_join_codes),
) -> str:
    """JSON for the on-screen widgets. Never needed in conversation."""
    if view == "dice":
        data = everyone.dice(log)
    elif view == "join" and codes is None:
        data = WEB_OFF
    elif view == "join" and codes is not None:
        with store.reading() as campaign:
            data = codes.view(campaign)
    elif view == "character" and not name:
        raise InvalidChangeError("The character view needs a name.")
    else:
        with store.reading() as campaign:
            if view == "character" and name:
                data = everyone.character(campaign, name)
            else:
                data = CAMPAIGN_VIEWS[view](campaign)
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


TOOLS: list[Callable[..., str]] = [get_screen_data]
