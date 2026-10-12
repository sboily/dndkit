"""Creating, changing and removing player characters."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from gamemaster_mcp.errors import InvalidChangeError
from gamemaster_mcp.game import registry, rules
from gamemaster_mcp.models import ABILITIES, Campaign, Character, now

KIND = "character"


def find(campaign: Campaign, ref: str) -> Character:
    """The character *ref* names (name or ID)."""
    return registry.find(campaign.characters, ref, KIND)


@dataclass(frozen=True)
class Spellcasting:
    """How a character casts: the ability, the spell attack bonus and the save DC."""

    ability: str
    attack: int
    save_dc: int


def pick(campaign: Campaign, ref: str | None) -> Character:
    """The character *ref* names; without one, whose turn it is, or the only character."""
    if ref:
        return find(campaign, ref)
    current = campaign.game_state.current_combatant
    if current is not None and current.character_id in campaign.characters:
        return campaign.characters[current.character_id]
    if len(campaign.characters) == 1:
        return next(iter(campaign.characters.values()))
    names = registry.known_names(campaign.characters.values())
    raise InvalidChangeError(f"Which character? Characters: {names}.")


def create(campaign: Campaign, character: Character) -> Character:
    """Add a character with what its class and level give: proficiency, hit dice, a
    caster's slots and casting ability. The name must be free."""
    cls = character.character_class
    if character.spellcasting_ability is None:
        character.spellcasting_ability = rules.casting_ability(cls.name)
    die = rules.hit_die(cls.name)
    character.character_class = cls.model_copy(update={"hit_dice": f"1d{die}"})
    character.hit_dice_remaining = f"{cls.level}d{die}"
    character.proficiency_bonus = rules.proficiency_bonus(cls.level)
    if not character.spell_slots:
        character.spell_slots = rules.spell_slots_for(cls.name, cls.level) or {}
    return registry.add(campaign.characters, character, KIND)


def level_edits(character: Character, level: int) -> dict[str, Any]:
    """What follows a level set by hand: proficiency, hit dice and spell slots (spent
    ones stay spent). Hit points do not: ``level_up`` gains a level in full."""
    cls = character.character_class
    die = rules.hit_die(cls.name)
    edits: dict[str, Any] = {
        "character_class": {**cls.model_dump(), "level": level, "hit_dice": f"1d{die}"},
        "proficiency_bonus": rules.proficiency_bonus(level),
        "hit_dice_remaining": f"{level}d{die}",
    }
    slots = rules.spell_slots_for(cls.name, level)
    if slots is not None:
        edits["spell_slots"] = dict(slots)
        edits["spell_slots_used"] = slots_still_used(character, slots)
    return edits


def slots_still_used(character: Character, slots: Mapping[int, int]) -> dict[int, int]:
    """The spent slots that remain spent once the character has *slots*."""
    used = character.spell_slots_used
    return {lvl: min(count, slots[lvl]) for lvl, count in used.items() if lvl in slots}


def spellcasting(character: Character) -> Spellcasting | None:
    """Spell attack bonus and save DC (PHB ch. 10); None for a character who casts nothing."""
    ability = _ability_name(character.spellcasting_ability) or rules.casting_ability(
        character.character_class.name
    )
    if ability is None or ability not in character.abilities:
        return None
    bonus = character.proficiency_bonus + character.abilities[ability].mod
    return Spellcasting(ability, bonus, 8 + bonus)


def initiative(character: Character) -> int:
    """The initiative bonus: the Dexterity modifier."""
    dexterity = character.abilities.get("dexterity")
    return dexterity.mod if dexterity else 0


_FRENCH_ABILITIES = {"for": "strength", "sag": "wisdom"}


def _ability_name(text: str | None) -> str | None:
    """ "INT", "Intelligence" or French "Sagesse" -> the ability's name."""
    if not text:
        return None
    wanted = registry.normalize(text)[:3]
    found = next((a for a in ABILITIES if a.startswith(wanted)), None)
    return found or _FRENCH_ABILITIES.get(wanted)


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
        edits.update(level_edits(character, level))
    if character.hit_points_current == 0 and edits.get("hit_points_current", 0) > 0:
        # Back from 0 HP by hand (a spell that raises the dead): a fresh start.
        edits.update(death_saves_success=0, death_saves_failure=0)
        edits.setdefault("conditions", [c for c in character.conditions if c != "unconscious"])
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
    if delta > 0 and character.death_saves_failure >= 3:
        raise InvalidChangeError(
            f"{character.name} is dead: healing does not bring them back. If a spell does "
            "(revivify, raise dead), set their hit points with update_character."
        )
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
