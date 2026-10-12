"""Skill and saving throw proficiencies (PHB ch. 7): the names players say, in
English or French, and the bonus each gives (ability modifier + proficiency)."""

from collections.abc import Sequence
from dataclasses import dataclass

from gamemaster_mcp.errors import InvalidChangeError
from gamemaster_mcp.game import rules
from gamemaster_mcp.game.tables import SKILL_ALIASES, SKILLS
from gamemaster_mcp.models import Character
from gamemaster_mcp.text import normalize


@dataclass(frozen=True)
class Proficiency:
    """A proficient skill or saving throw and its bonus; None for a skill the rules
    do not know (a sheet from elsewhere)."""

    name: str
    bonus: int | None


def skill_name(text: str) -> str | None:
    """ "stealth", "Discrétion" -> "Stealth"; None for anything else."""
    wanted = normalize(text)
    found = next((skill for skill in SKILLS if normalize(skill) == wanted), None)
    return found or SKILL_ALIASES.get(wanted)


def skills(names: Sequence[str]) -> list[str]:
    """The skills *names* say, by their English names; one error lists the unknown."""
    found = {name: skill_name(name) for name in names}
    unknown = [name for name, skill in found.items() if skill is None]
    if unknown:
        raise InvalidChangeError(
            f"Unknown skills: {', '.join(unknown)}. Skills (English or French names): "
            f"{', '.join(SKILLS)}."
        )
    return list(dict.fromkeys(skill for skill in found.values() if skill))


def saves(names: Sequence[str]) -> list[str]:
    """The abilities *names* say ("DEX", "Sagesse"); one error lists the unknown."""
    found = {name: rules.ability_name(name) for name in names}
    unknown = [name for name, ability in found.items() if ability is None]
    if unknown:
        raise InvalidChangeError(f"Unknown saving throws: {', '.join(unknown)}; use STR to CHA.")
    return list(dict.fromkeys(ability for ability in found.values() if ability))


def skill_bonuses(character: Character) -> list[Proficiency]:
    """Each proficient skill with its bonus, as the sheet lists them."""
    shown: list[Proficiency] = []
    for name in character.skill_proficiencies:
        skill = skill_name(name)
        ability = SKILLS[skill] if skill else None
        shown.append(Proficiency(skill or name, _bonus(character, ability)))
    return shown


def save_bonuses(character: Character) -> list[Proficiency]:
    """Each proficient saving throw with its bonus."""
    abilities = [rules.ability_name(name) for name in character.saving_throw_proficiencies]
    return [Proficiency(a, _bonus(character, a)) for a in abilities if a]


def save_bonus(character: Character, ability: str) -> int:
    """A saving throw's bonus: the modifier, plus proficiency where the sheet has it."""
    score = character.abilities.get(ability)
    proficient = ability in {rules.ability_name(n) for n in character.saving_throw_proficiencies}
    return (score.mod if score else 0) + (character.proficiency_bonus if proficient else 0)


def _bonus(character: Character, ability: str | None) -> int | None:
    if ability is None:
        return None
    score = character.abilities.get(ability)
    return (score.mod if score else 0) + character.proficiency_bonus
