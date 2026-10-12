"""Battle map tools: lay out the map, put combatants on it, move them by the rules."""

from collections.abc import Callable
from typing import Annotated

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from pydantic import Field

from gamemaster_mcp.game import battlefield, combat, movement
from gamemaster_mcp.game.movement import Order
from gamemaster_mcp.models import Placement
from gamemaster_mcp.models.battle import MAX_SQUARES
from gamemaster_mcp.storage import CampaignStore
from gamemaster_mcp.tools import render_map
from gamemaster_mcp.tools.apps import COMBAT_APP, app_meta
from gamemaster_mcp.tools.deps import get_store

Squares = Annotated[list[str] | None, Field(description='Squares: "C3", or "C1:C6" for a block')]
Creature = Annotated[str | None, Field(description="A combatant")]


@tool(meta=app_meta(COMBAT_APP))
def set_battlefield(
    width: Annotated[int, Field(ge=1, le=MAX_SQUARES, description="Squares across, 5 ft each")],
    height: Annotated[int, Field(ge=1, le=MAX_SQUARES, description="Squares down")],
    walls: Squares = None,
    difficult: Squares = None,
    store: CampaignStore = Depends(get_store),
) -> str:
    """Lay out the battle map (A1 top left) with walls and difficult terrain. Whoever
    has no square yet is placed: the party on the left edge, foes on the right."""
    with store.transaction() as campaign:
        state = campaign.game_state
        battlefield.lay_out(state, width, height, walls or [], difficult or [])
        battlefield.place_the_rest(state)
        return render_map.battle_map(campaign)


@tool
def place_tokens(
    tokens: Annotated[list[Placement], Field(min_length=1, description="Who stands where")],
    store: CampaignStore = Depends(get_store),
) -> str:
    """Put combatants on chosen squares (an ambush, a formation); a big creature by its
    top-left square."""
    with store.transaction() as campaign:
        state = campaign.game_state
        for token in tokens:
            combatant = combat.find(state, token.who)
            combatant.position = None
            if token.ally is not None:
                combatant.ally = token.ally
            battlefield.place(state, combatant, token.at)
        return render_map.battle_map(campaign)


@tool
def move_token(
    who: Annotated[str, Field(min_length=1, description="The combatant moving")],
    to: Annotated[str | None, Field(description="Square, e.g. D7")] = None,
    toward: Creature = None,
    away_from: Creature = None,
    feet: Annotated[int | None, Field(ge=5, description="At most this far")] = None,
    dash: Annotated[bool, Field(description="Dash: double movement this turn")] = False,
    disengage: Annotated[bool, Field(description="Disengage: no opportunity attacks")] = False,
    forced: Annotated[bool, Field(description="Pushed, pulled or teleported")] = False,
    store: CampaignStore = Depends(get_store),
) -> str:
    """Move by the 5e rules: speed, terrain, others in the way, standing up. Says the cost,
    what is left, the opportunity attacks provoked and who is in reach. Refuses an
    impossible move. toward stops within reach of the creature."""
    order = Order(to=to, toward=toward, away_from=away_from, feet=feet)
    with store.transaction() as campaign:
        done = movement.move(campaign, who, order, dash=dash, disengage=disengage, forced=forced)
        return render_map.move(campaign, done)


TOOLS: list[Callable[..., str]] = [set_battlefield, place_tokens, move_token]
