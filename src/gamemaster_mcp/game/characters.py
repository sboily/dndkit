"""Creating, changing and removing player characters."""

from collections.abc import Mapping, Sequence
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


def adjust(
    campaign: Campaign,
    refs: Sequence[str],
    *,
    hp_change: int | None = None,
    temp_hp_change: int | None = None,
    ability_changes: Mapping[str, int] | None = None,
) -> list[str]:
    """Apply the same relative change to several characters; one line per character.

    Every name is checked before anything changes, so a misheard name changes
    no one.
    """
    targets = registry.find_many(campaign.characters, refs, KIND)
    deltas = dict(ability_changes or {})
    unknown = sorted(set(deltas) - set(ABILITIES))
    if unknown:
        raise InvalidChangeError(f"Unknown abilities: {', '.join(unknown)}.")
    return [_adjust_one(c, hp_change, temp_hp_change, deltas) for c in targets]


def _adjust_one(
    character: Character,
    hp_change: int | None,
    temp_hp_change: int | None,
    ability_changes: Mapping[str, int],
) -> str:
    notes: list[str] = []
    if temp_hp_change:
        character.temporary_hit_points = max(0, character.temporary_hit_points + temp_hp_change)
        notes.append(f"temporary HP {character.temporary_hit_points}")
    if hp_change:
        notes.append(_change_hp(character, hp_change))
    for ability, delta in ability_changes.items():
        score = character.abilities[ability]
        score.score = max(1, min(30, score.score + delta))
        notes.append(f"{ability} {score.score}")
    character.updated_at = now()
    return f"{character.name}: {', '.join(notes) or 'no change'}"


def _change_hp(character: Character, delta: int) -> str:
    """Heal or damage one character, following the 0 HP rules."""
    was_down = character.hit_points_current == 0
    hp = rules.apply_hp_change(
        character.hit_points_current,
        character.hit_points_max,
        character.temporary_hit_points,
        delta,
    )
    character.hit_points_current = hp.current
    character.temporary_hit_points = hp.temporary
    status = f"HP {hp.current}/{character.hit_points_max}"
    if was_down and hp.current > 0:
        character.death_saves_success = 0
        character.death_saves_failure = 0
        return f"{status}, conscious again (death saves reset)"
    if hp.current == 0 and delta < 0:
        if not was_down:
            return f"{status}, down and making death saving throws"
        character.death_saves_failure = min(3, character.death_saves_failure + 1)
        return f"{status}, hit while down: {character.death_saves_failure}/3 death save failures"
    return status
