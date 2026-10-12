"""Battle map tools: lay out the map, put combatants on it, move them by the rules."""

from collections.abc import Callable
from typing import Annotated

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from pydantic import Field

from dndkit.game import areas, battlefield, combat, movement, sight
from dndkit.game.areas import Aim, Shape
from dndkit.game.movement import Order
from dndkit.models import Placement
from dndkit.models.battle import MAX_SQUARES
from dndkit.storage import CampaignStore
from dndkit.tools import render_combat, render_map
from dndkit.tools.apps import COMBAT_APP, app_meta
from dndkit.tools.deps import READ_ONLY, get_store

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
    """Lay out the battle map (A1 top left). Whoever has no square goes to an edge:
    the party left, foes right."""
    with store.transaction() as campaign:
        state = campaign.game_state
        battlefield.lay_out(state, width, height, walls or [], difficult or [])
        battlefield.place_the_rest(state)
        return render_map.battle_map(campaign)


@tool
def place_tokens(
    tokens: Annotated[list[Placement], Field(min_length=1, description="Who and where")],
    store: CampaignStore = Depends(get_store),
) -> str:
    """Put combatants on squares (big ones by their top-left square), or hide them from
    the players (an ambush) and reveal them. remove_combatant takes one off."""
    with store.transaction() as campaign:
        state = campaign.game_state
        for token in tokens:
            combatant = combat.find(state, token.who)
            if token.ally is not None:
                combatant.ally = token.ally
            if token.hidden is not None:
                combatant.hidden = token.hidden
            if token.at is not None:
                combatant.position = None
                battlefield.place(state, combatant, token.at)
        if state.battlefield is None:
            return render_combat.initiative(campaign)
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
    """Move by the 5e rules; says the cost, movement left, opportunity attacks and who is
    in reach. Refuses impossible moves; toward stops within reach."""
    order = Order(to=to, toward=toward, away_from=away_from, feet=feet)
    with store.transaction() as campaign:
        done = movement.move(campaign, who, order, dash=dash, disengage=disengage, forced=forced)
        return render_map.move(campaign, done)


@tool
def area_of_effect(
    shape: Annotated[Shape, Field(description="sphere also for cylinders")],
    feet: Annotated[int, Field(ge=5, description="Radius, cube side, or cone/line length")],
    at: Annotated[str | None, Field(description="Centre: square or creature")] = None,
    source: Annotated[str | None, Field(description="Caster of a cone, line or cube")] = None,
    toward: Annotated[str | None, Field(description="Square or creature aimed at")] = None,
    width: Annotated[int, Field(ge=5, description="Line width")] = 5,
    store: CampaignStore = Depends(get_store),
) -> str:
    """Who an area of effect catches; walls stop it. Shown until the next turn."""
    aim = Aim(shape=shape, feet=feet, at=at, source=source, toward=toward, width=width)
    with store.transaction() as campaign:
        return render_map.area(areas.resolve(campaign.game_state, aim))


@tool(annotations=READ_ONLY)
def check_target(
    attacker: Annotated[str, Field(min_length=1, description="Who attacks")],
    target: Annotated[str, Field(min_length=1, description="Who is attacked")],
    store: CampaignStore = Depends(get_store),
) -> str:
    """Before an attack on the map: distance, reach, cover, and what gives disadvantage."""
    with store.reading() as campaign:
        return render_map.sightline(sight.look(campaign, attacker, target))


TOOLS: list[Callable[..., str]] = [
    set_battlefield,
    place_tokens,
    move_token,
    area_of_effect,
    check_target,
]
