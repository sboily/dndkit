"""Character resource tools: inventory, death saves and rests."""

from collections.abc import Callable
from typing import Annotated, Literal

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from pydantic import Field

from dndkit.game import resources, rests
from dndkit.game.dice import DiceLog
from dndkit.game.resources import DeathSave
from dndkit.game.rests import RestKind
from dndkit.models import Item
from dndkit.storage import CampaignStore
from dndkit.tools.deps import NameOrId, get_dice_log, get_store


@tool
def add_item_to_character(
    character_name_or_id: NameOrId,
    item_name: Annotated[str, Field(min_length=1, description="Item name")],
    quantity: Annotated[int, Field(ge=1, description="How many")] = 1,
    item_type: Annotated[
        Literal["weapon", "armor", "consumable", "misc"], Field(description="Item type")
    ] = "misc",
    description: Annotated[str | None, Field(description="Item description")] = None,
    weight: Annotated[float | None, Field(ge=0, description="Weight in pounds")] = None,
    value: Annotated[str | None, Field(description="Value, e.g. '50 gp'")] = None,
    store: CampaignStore = Depends(get_store),
) -> str:
    """Give items to a character. Items already carried stack."""
    item = Item(
        name=item_name.strip(),
        quantity=quantity,
        item_type=item_type,
        description=description,
        weight=weight,
        value=value,
    )
    with store.transaction() as campaign:
        character, held = resources.add_item(campaign, character_name_or_id, item)
    return f"{character.name} now carries {held.quantity} x {held.name}."


@tool
def remove_item_from_character(
    character_name_or_id: NameOrId,
    item_name: Annotated[str, Field(min_length=1, description="Item name")],
    quantity: Annotated[int, Field(ge=1, description="How many to remove")] = 1,
    store: CampaignStore = Depends(get_store),
) -> str:
    """Take items away from a character: used, sold, lost or given away."""
    with store.transaction() as campaign:
        character, item, left = resources.remove_item(
            campaign, character_name_or_id, item_name, quantity
        )
    return f"{character.name} has {left} x {item.name} left."


@tool
def record_death_save(
    character_name_or_id: NameOrId,
    outcome: Annotated[
        DeathSave,
        Field(
            description="success (10+), failure (2-9), nat20 (regain 1 HP), nat1 (two "
            "failures), stabilized (Spare the Dying, Medicine DC 10)"
        ),
    ],
    store: CampaignStore = Depends(get_store),
) -> str:
    """Record a death saving throw for a character at 0 HP."""
    with store.transaction() as campaign:
        return resources.record_death_save(campaign, character_name_or_id, outcome)


@tool
def rest(
    kind: Annotated[RestKind, Field(description="short (1 hour) or long (8 hours)")] = "long",
    names_or_ids: Annotated[
        list[str] | None, Field(description="Who rests; omit for the whole party")
    ] = None,
    hit_dice: Annotated[
        int, Field(ge=0, le=20, description="Short rest: Hit Dice each one spends to heal")
    ] = 0,
    store: CampaignStore = Depends(get_store),
    log: DiceLog = Depends(get_dice_log),
) -> str:
    """Rest. Long: full HP and slots, half the Hit Dice back, one exhaustion level less.
    Short: pact slots, and Hit Dice spent heal (rolled here)."""
    with store.transaction() as campaign:
        rested = rests.rest(campaign, names_or_ids or [], kind, hit_dice)
    for roll in rested.rolls:
        log.record(roll)
    return "\n".join(rested.lines) or "No characters to rest."


TOOLS: list[Callable[..., str]] = [
    add_item_to_character,
    remove_item_from_character,
    record_death_save,
    rest,
]
