"""Character resource tools: inventory, spell slots, death saves and rests."""

from collections.abc import Callable
from typing import Annotated, Literal

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from pydantic import Field

from gamemaster_mcp.game import resources
from gamemaster_mcp.game.resources import DeathSave
from gamemaster_mcp.models import Item
from gamemaster_mcp.storage import CampaignStore
from gamemaster_mcp.tools.deps import NameOrId, get_store

SpellLevel = Annotated[int, Field(ge=1, le=9, description="Spell slot level (1-9)")]


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
def set_spell_slots(
    character_name_or_id: NameOrId,
    level: SpellLevel,
    max_slots: Annotated[int, Field(ge=0, le=9, description="Slots at this level; 0 removes")],
    store: CampaignStore = Depends(get_store),
) -> str:
    """Set how many spell slots a character has at one level."""
    with store.transaction() as campaign:
        character = resources.set_spell_slots(campaign, character_name_or_id, level, max_slots)
    return f"{character.name}'s spell slots: {resources.describe_slots(character)}."


@tool
def use_spell_slot(
    character_name_or_id: NameOrId,
    level: SpellLevel,
    store: CampaignStore = Depends(get_store),
) -> str:
    """Spend one spell slot when a character casts a levelled spell."""
    with store.transaction() as campaign:
        character, left = resources.use_spell_slot(campaign, character_name_or_id, level)
    return f"{character.name} has {left} level {level} slot(s) left."


@tool
def record_death_save(
    character_name_or_id: NameOrId,
    outcome: Annotated[
        DeathSave,
        Field(
            description="success (10+), failure (2-9), nat20 (regain 1 HP) or nat1 (two failures)"
        ),
    ],
    store: CampaignStore = Depends(get_store),
) -> str:
    """Record a death saving throw for a character at 0 HP."""
    with store.transaction() as campaign:
        return resources.record_death_save(campaign, character_name_or_id, outcome)


@tool
def long_rest(
    names_or_ids: Annotated[
        list[str] | None, Field(description="Who rests; omit for the whole party")
    ] = None,
    store: CampaignStore = Depends(get_store),
) -> str:
    """Long rest: full hit points, spell slots back, temporary HP and death saves cleared."""
    with store.transaction() as campaign:
        lines = resources.long_rest(campaign, names_or_ids or [])
    return "\n".join(lines) or "No characters to rest."


TOOLS: list[Callable[..., str]] = [
    add_item_to_character,
    remove_item_from_character,
    set_spell_slots,
    use_spell_slot,
    record_death_save,
    long_rest,
]
