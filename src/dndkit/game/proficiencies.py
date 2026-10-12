"""Skill and saving throw proficiencies (PHB ch. 7): the names players say, in
English or French, and the bonus each gives (ability modifier + proficiency,
twice the proficiency with Expertise)."""

from collections.abc import Sequence
from dataclasses import dataclass

from dndkit.errors import InvalidChangeError
from dndkit.game import rules
from dndkit.game.tables import SKILL_ALIASES, SKILLS
from dndkit.models import Character
from dndkit.text import normalize


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


def expertise(names: Sequence[str], proficient: Sequence[str]) -> list[str]:
    """The skills *names* say, each one among *proficient*: Expertise (a rogue's, a
    bard's) doubles a proficiency the character has."""
    chosen = skills(names)
    have = {skill_name(name) for name in proficient}
    missing = [skill for skill in chosen if skill not in have]
    if missing:
        raise InvalidChangeError(
            f"Expertise doubles a proficiency, and {', '.join(missing)} is not among the "
            "proficient skills: give it in skills too."
        )
    return chosen


def jack_of_all_trades(character: Character) -> int:
    """A bard's half proficiency, rounded down, on the checks it is not proficient in
    (initiative included), from level 2."""
    cls = character.character_class
    if rules.class_key(cls.name) == "bard" and cls.level >= 2:
        return character.proficiency_bonus // 2
    return 0


def skill_bonuses(character: Character) -> list[Proficiency]:
    """Each proficient skill with its bonus, as the sheet lists them."""
    experts = {skill_name(name) for name in character.skill_expertise}
    shown: list[Proficiency] = []
    for name in character.skill_proficiencies:
        skill = skill_name(name)
        ability = SKILLS[skill] if skill else None
        times = 2 if skill and skill in experts else 1
        shown.append(Proficiency(skill or name, _bonus(character, ability, times)))
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


def _bonus(character: Character, ability: str | None, times: int = 1) -> int | None:
    if ability is None:
        return None
    score = character.abilities.get(ability)
    return (score.mod if score else 0) + times * character.proficiency_bonus
