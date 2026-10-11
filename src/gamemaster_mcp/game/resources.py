"""What characters carry and recover: items, death saves, rests."""

from collections.abc import Sequence
from typing import Literal

from gamemaster_mcp.errors import InvalidChangeError, NotFoundError
from gamemaster_mcp.game import characters, registry, rules
from gamemaster_mcp.models import Campaign, Character, Item, now

DeathSave = Literal["success", "failure", "nat20", "nat1"]
RestKind = Literal["short", "long"]


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
        character.conditions = [c for c in character.conditions if c != "unconscious"]
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


def rest(campaign: Campaign, refs: Sequence[str], kind: RestKind) -> list[str]:
    """A short or long rest for the named characters, or everyone when *refs* is empty."""
    targets = (
        registry.find_many(campaign.characters, refs, characters.KIND)
        if refs
        else list(campaign.characters.values())
    )
    rest_one = _long_rest if kind == "long" else _short_rest
    return [rest_one(character) for character in targets]


def _long_rest(character: Character) -> str:
    """PHB ch. 8: needs at least 1 HP when the rest starts."""
    if character.hit_points_current == 0:
        return f"{character.name} is at 0 HP and gains nothing from the rest"
    character.hit_points_current = character.hit_points_max
    character.temporary_hit_points = 0
    character.spell_slots_used = {}
    character.exhaustion = max(0, character.exhaustion - 1)
    _reset_death_saves(character)
    character.updated_at = now()
    exhaustion = f", exhaustion {character.exhaustion}" if character.exhaustion else ""
    return f"{character.name}: HP {character.hit_points_max}, spell slots restored{exhaustion}"


def _short_rest(character: Character) -> str:
    """Warlocks get their pact slots back; healing comes from Hit Dice the player rolls."""
    if rules.class_key(character.character_class.name) == "warlock":
        character.spell_slots_used = {}
        character.updated_at = now()
        return f"{character.name}: pact slots restored; may spend Hit Dice to heal"
    return f"{character.name}: may spend Hit Dice ({character.hit_dice_remaining}) to heal"
