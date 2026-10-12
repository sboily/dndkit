"""Spell slots and the spells a character knows."""

from collections.abc import Mapping
from typing import Any

from dndkit.errors import InvalidChangeError, NotFoundError
from dndkit.game import characters, registry
from dndkit.models import Campaign, Character, Spell, now


def set_spell_slots(campaign: Campaign, ref: str, level: int, max_slots: int) -> Character:
    """Set how many slots of *level* a character has; 0 removes the level."""
    character = characters.find(campaign, ref)
    if max_slots == 0:
        character.spell_slots.pop(level, None)
        character.spell_slots_used.pop(level, None)
    else:
        character.spell_slots[level] = max_slots
        used = character.spell_slots_used.get(level, 0)
        character.spell_slots_used[level] = min(used, max_slots)
    character.updated_at = now()
    return character


def use_spell_slot(campaign: Campaign, ref: str, level: int) -> tuple[Character, int]:
    """Spend one slot of *level*; returns the character and the slots left."""
    character = characters.find(campaign, ref)
    maximum = character.spell_slots.get(level, 0)
    if maximum == 0:
        raise InvalidChangeError(
            f"{character.name} has no level {level} spell slots. "
            f"Slots: {describe_slots(character)}."
        )
    used = character.spell_slots_used.get(level, 0)
    if used >= maximum:
        raise InvalidChangeError(
            f"{character.name} has no level {level} slot left ({used}/{maximum} used)."
        )
    character.spell_slots_used[level] = used + 1
    character.updated_at = now()
    return character, maximum - used - 1


def describe_slots(character: Character) -> str:
    """Slots left per level, e.g. "level 1: 2/4, level 2: 1/2"."""
    if not character.spell_slots:
        return "none"
    return ", ".join(
        f"level {level}: {maximum - character.spell_slots_used.get(level, 0)}/{maximum}"
        for level, maximum in sorted(character.spell_slots.items())
    )


def set_known_spell(
    campaign: Campaign, ref: str, spell_name: str, changes: Mapping[str, Any]
) -> tuple[Character, Spell, bool]:
    """Add a spell to a character's list, or change one already there.

    Returns the character, the spell and whether it is new. A new spell needs
    its level (0 for a cantrip).
    """
    character = characters.find(campaign, ref)
    spell = _known(character, spell_name)
    if spell is None:
        if changes.get("level") is None:
            raise InvalidChangeError(
                f"{character.name} doesn't know '{spell_name}' yet: give its level "
                "(0 for a cantrip) to add it."
            )
        spell = Spell(name=spell_name.strip(), **changes)
        character.spells_known = [*character.spells_known, spell]
        created = True
    else:
        updated = registry.revised(spell, changes)
        character.spells_known = [updated if s is spell else s for s in character.spells_known]
        spell, created = updated, False
    character.updated_at = now()
    return character, spell, created


def forget_spell(campaign: Campaign, ref: str, spell_name: str) -> tuple[Character, Spell]:
    """Remove a spell from a character's list."""
    character = characters.find(campaign, ref)
    spell = _known(character, spell_name)
    if spell is None:
        raise NotFoundError(
            f"{character.name} doesn't know '{spell_name}'. "
            f"Known spells: {registry.known_names(character.spells_known)}."
        )
    character.spells_known = [s for s in character.spells_known if s is not spell]
    character.updated_at = now()
    return character, spell


def _known(character: Character, name: str) -> Spell | None:
    wanted = registry.normalize(name)
    return next((s for s in character.spells_known if registry.normalize(s.name) == wanted), None)
