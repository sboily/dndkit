"""Spell tools: slots and the spells a character knows."""

from collections.abc import Callable
from typing import Annotated

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from pydantic import Field

from dndkit.game import spellbook
from dndkit.storage import CampaignStore
from dndkit.tools.deps import NameOrId, get_store, provided

SpellLevel = Annotated[int, Field(ge=1, le=9, description="Spell slot level (1-9)")]


@tool
def set_spell_slots(
    character_name_or_id: NameOrId,
    level: SpellLevel,
    max_slots: Annotated[int, Field(ge=0, le=9, description="Slots at this level; 0 removes")],
    store: CampaignStore = Depends(get_store),
) -> str:
    """Set how many spell slots a character has at one level (level_up does it by class)."""
    with store.transaction() as campaign:
        character = spellbook.set_spell_slots(campaign, character_name_or_id, level, max_slots)
    return f"{character.name}'s spell slots: {spellbook.describe_slots(character)}."


@tool
def use_spell_slot(
    character_name_or_id: NameOrId,
    level: SpellLevel,
    store: CampaignStore = Depends(get_store),
) -> str:
    """Spend one spell slot when a character casts a levelled spell."""
    with store.transaction() as campaign:
        character, left = spellbook.use_spell_slot(campaign, character_name_or_id, level)
    return f"{character.name} has {left} level {level} slot(s) left."


@tool
def set_known_spell(
    character_name_or_id: NameOrId,
    spell: Annotated[str, Field(min_length=1, description="Spell name")],
    level: Annotated[int | None, Field(ge=0, le=9, description="0 for a cantrip")] = None,
    prepared: Annotated[bool | None, Field(description="Prepared today")] = None,
    description: Annotated[str | None, Field(description="Short reminder of its effect")] = None,
    forget: Annotated[bool, Field(description="Remove it from the list")] = False,
    store: CampaignStore = Depends(get_store),
) -> str:
    """Add, change or remove (forget=true) a spell on a character's spell list."""
    with store.transaction() as campaign:
        if forget:
            character, known = spellbook.forget_spell(campaign, character_name_or_id, spell)
            return f"{character.name} no longer knows {known.name}."
        changes = provided(level=level, prepared=prepared, description=description)
        character, known, created = spellbook.set_known_spell(
            campaign, character_name_or_id, spell, changes
        )
    verb = "learns" if created else "updates"
    level_text = "cantrip" if known.level == 0 else f"level {known.level}"
    prepared_text = ", prepared" if known.prepared else ""
    return f"{character.name} {verb} {known.name} ({level_text}{prepared_text})."


TOOLS: list[Callable[..., str]] = [set_spell_slots, use_spell_slot, set_known_spell]
