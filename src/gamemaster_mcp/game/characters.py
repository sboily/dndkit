"""Creating, changing and removing player characters."""

from collections.abc import Mapping
from typing import Any

from gamemaster_mcp.errors import InvalidChangeError
from gamemaster_mcp.game import registry, rules
from gamemaster_mcp.models import ABILITIES, Campaign, Character, now

KIND = "character"


def find(campaign: Campaign, ref: str) -> Character:
    """The character *ref* names (name or ID)."""
    return registry.find(campaign.characters, ref, KIND)


def create(campaign: Campaign, character: Character) -> Character:
    """Add a character; the name must be free."""
    return registry.add(campaign.characters, character, KIND)


def remove(campaign: Campaign, ref: str) -> Character:
    """Remove a character from the campaign."""
    return registry.remove(campaign.characters, ref, KIND)


def update(
    campaign: Campaign,
    ref: str,
    changes: Mapping[str, Any],
    abilities: Mapping[str, int],
) -> Character:
    """Apply sheet changes; ``class_level`` and ability scores go to their nested fields."""
    character = find(campaign, ref)
    edits = dict(changes)
    level = edits.pop("class_level", None)
    if level is not None:
        edits["character_class"] = {**character.character_class.model_dump(), "level": level}
    if abilities:
        unknown = sorted(set(abilities) - set(ABILITIES))
        if unknown:
            raise InvalidChangeError(f"Unknown abilities: {', '.join(unknown)}.")
        scores = {name: score.model_dump() for name, score in character.abilities.items()}
        scores.update({name: {"score": value} for name, value in abilities.items()})
        edits["abilities"] = scores
    _cap_hit_points(character, edits)
    edits["updated_at"] = now()
    return registry.update(campaign.characters, character.id, KIND, edits)


def _cap_hit_points(character: Character, edits: dict[str, Any]) -> None:
    """Refuse current HP above the maximum; a lowered maximum lowers current HP."""
    maximum = edits.get("hit_points_max", character.hit_points_max)
    current = edits.get("hit_points_current")
    if current is None:
        edits["hit_points_current"] = min(character.hit_points_current, maximum)
    elif current > maximum:
        raise InvalidChangeError(
            f"{character.name}'s current HP ({current}) cannot exceed max HP ({maximum})."
        )


def change_hp(character: Character, delta: int) -> str:
    """Heal or damage one character, following the 0 HP rules (PHB ch. 9)."""
    was_down = character.hit_points_current == 0
    hp = rules.apply_hp_change(
        character.hit_points_current,
        character.hit_points_max,
        character.temporary_hit_points,
        delta,
    )
    overflow = -delta - (character.temporary_hit_points - hp.temporary)
    overflow -= character.hit_points_current
    character.hit_points_current = hp.current
    character.temporary_hit_points = hp.temporary
    character.updated_at = now()
    status = f"{character.name}: HP {hp.current}/{character.hit_points_max}"
    if delta > 0:
        return _healed(character, status) if was_down and hp.current > 0 else status
    if hp.current > 0:
        return status
    if overflow >= character.hit_points_max:
        character.death_saves_failure = 3
        return f"{status}, killed outright by massive damage"
    if was_down:
        character.death_saves_failure = min(3, character.death_saves_failure + 1)
        return f"{status}, hit while down: {character.death_saves_failure}/3 death save failures"
    _add_conditions(character, "unconscious", "prone")
    return f"{status}, unconscious and prone: death saving throws from now on"


def _healed(character: Character, status: str) -> str:
    character.death_saves_success = 0
    character.death_saves_failure = 0
    character.conditions = [c for c in character.conditions if c != "unconscious"]
    return f"{status}, conscious again (still prone; death saves reset)"


def _add_conditions(character: Character, *names: str) -> None:
    character.conditions = [
        *character.conditions,
        *(n for n in names if n not in character.conditions),
    ]
