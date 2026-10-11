"""What characters spend and recover: items, spell slots, death saves, rests."""

from collections.abc import Sequence
from typing import Literal

from gamemaster_mcp.errors import InvalidChangeError, NotFoundError
from gamemaster_mcp.game import characters, registry
from gamemaster_mcp.models import Campaign, Character, Item, now

DeathSave = Literal["success", "failure", "nat20", "nat1"]


def add_item(campaign: Campaign, ref: str, item: Item) -> tuple[Character, Item]:
    """Give an item; one already held (same name and type) stacks."""
    character = characters.find(campaign, ref)
    held = _held(character, item.name)
    if held is not None and held.item_type == item.item_type:
        held.quantity += item.quantity
        item = held
    else:
        character.inventory.append(item)
    character.updated_at = now()
    return character, item


def remove_item(
    campaign: Campaign, ref: str, item_name: str, quantity: int
) -> tuple[Character, Item, int]:
    """Take *quantity* of an item; returns the character, the item and what is left."""
    character = characters.find(campaign, ref)
    held = _held(character, item_name)
    if held is None:
        raise NotFoundError(
            f"{character.name} has no '{item_name}'. "
            f"Inventory: {registry.known_names(character.inventory)}."
        )
    if quantity > held.quantity:
        raise InvalidChangeError(f"{character.name} has only {held.quantity} x {held.name}.")
    remaining = held.quantity - quantity
    if remaining:
        held.quantity = remaining
    else:
        character.inventory = [item for item in character.inventory if item is not held]
    character.updated_at = now()
    return character, held, remaining


def _held(character: Character, name: str) -> Item | None:
    wanted = registry.normalize(name)
    return next((i for i in character.inventory if registry.normalize(i.name) == wanted), None)


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


def record_death_save(campaign: Campaign, ref: str, outcome: DeathSave) -> str:
    """Record one death saving throw (PHB ch. 9) and say where it leaves the character."""
    character = characters.find(campaign, ref)
    if character.hit_points_current > 0:
        raise InvalidChangeError(
            f"{character.name} has {character.hit_points_current} HP; "
            "death saves are rolled at 0 HP only."
        )
    if character.death_saves_failure >= 3:
        raise InvalidChangeError(f"{character.name} is dead (3 failed death saves).")
    character.updated_at = now()
    if outcome == "nat20":
        character.hit_points_current = 1
        _reset_death_saves(character)
        return f"{character.name} rolls a natural 20, regains 1 HP and is conscious."
    if outcome == "success":
        character.death_saves_success += 1
    else:
        failures = 2 if outcome == "nat1" else 1
        character.death_saves_failure = min(3, character.death_saves_failure + failures)
    if character.death_saves_failure >= 3:
        return f"{character.name} dies (3 failed death saves)."
    if character.death_saves_success >= 3:
        _reset_death_saves(character)
        return f"{character.name} is stable at 0 HP."
    return (
        f"{character.name}: {character.death_saves_success} successes, "
        f"{character.death_saves_failure} failures."
    )


def _reset_death_saves(character: Character) -> None:
    character.death_saves_success = 0
    character.death_saves_failure = 0


def long_rest(campaign: Campaign, refs: Sequence[str]) -> list[str]:
    """Long rest for the named characters, or everyone when *refs* is empty.

    A character needs at least 1 HP when the rest starts to benefit (PHB ch. 8).
    """
    targets = (
        registry.find_many(campaign.characters, refs, characters.KIND)
        if refs
        else list(campaign.characters.values())
    )
    lines: list[str] = []
    for character in targets:
        if character.hit_points_current == 0:
            lines.append(f"{character.name} is at 0 HP and gains nothing from the rest")
            continue
        character.hit_points_current = character.hit_points_max
        character.temporary_hit_points = 0
        character.spell_slots_used = {}
        _reset_death_saves(character)
        character.updated_at = now()
        lines.append(f"{character.name}: HP {character.hit_points_max}, spell slots restored")
    return lines
