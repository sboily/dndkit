"""D&D 5e rules the tools apply: hit points, experience, levels, encounters."""

from dataclasses import dataclass

from dndkit.game.tables import (
    CASTING_ABILITY,
    CLASS_ALIASES,
    CLASS_SAVES,
    CLASSES,
    DIFFICULTY_THRESHOLDS,
    ENCOUNTER_MULTIPLIERS,
    FULL_CASTER_SLOTS,
    MONSTER_STATS,
    PACT_SLOTS,
    SLOW_RACES,
    XP_BY_CHALLENGE,
    XP_FOR_LEVEL,
)
from dndkit.models import ABILITIES
from dndkit.text import normalize

_FRENCH_ABILITIES = {"for": "strength", "sag": "wisdom"}


@dataclass(frozen=True)
class HitPoints:
    """Hit points after a change."""

    current: int
    temporary: int


def apply_hp_change(current: int, maximum: int, temporary: int, delta: int) -> HitPoints:
    """Healing up to the maximum, or damage taken from temporary hit points first.

    Healing never restores temporary hit points (PHB, "Temporary Hit Points").
    """
    if delta >= 0:
        return HitPoints(current=min(maximum, current + delta), temporary=temporary)
    damage = -delta
    absorbed = min(temporary, damage)
    return HitPoints(current=max(0, current - (damage - absorbed)), temporary=temporary - absorbed)


def experience_per_character(total_xp: int, party_size: int) -> int:
    """XP each character earns: the monsters' total XP split evenly (DMG, ch. 3).

    The DMG's encounter multipliers rate an encounter's difficulty; they never
    change the XP awarded.
    """
    if party_size < 1:
        raise ValueError("party_size must be at least 1")
    return total_xp // party_size


def base_speed(race: str) -> int:
    """Walking speed for a race: 25 for dwarves, halflings and gnomes, else 30."""
    words = set(normalize(race).split())
    return 25 if words & SLOW_RACES else 30


def class_key(class_name: str) -> str | None:
    """The 5e class a name refers to ("Magicien" -> "wizard"), or None if homebrew."""
    name = normalize(class_name)
    key = CLASS_ALIASES.get(name, name)
    return key if key in CLASSES else None


def hit_die(class_name: str) -> int:
    """The class's hit die size; d8 for a class the rules do not know."""
    key = class_key(class_name)
    return CLASSES[key][0] if key else 8


def proficiency_bonus(level: int) -> int:
    """+2 at levels 1-4, up to +6 at 17-20."""
    return 2 + (max(1, level) - 1) // 4


def level_for_xp(xp: int) -> int:
    """The highest level *xp* experience points reach."""
    return max(level for level, needed in XP_FOR_LEVEL.items() if xp >= needed)


def challenge_key(challenge: str) -> str:
    """A challenge rating as the tables write it ("0.25" -> "1/4")."""
    text = challenge.strip().replace(",", ".")
    return {"0.125": "1/8", "0.25": "1/4", "0.5": "1/2"}.get(text, text)


def xp_for_challenge(challenge: str) -> int | None:
    """Monster XP for a challenge rating ("1/4", "0.25", "3"), None if unknown."""
    return XP_BY_CHALLENGE.get(challenge_key(challenge))


@dataclass(frozen=True)
class MonsterStats:
    """What a monster of some challenge rating should have (DMG ch. 9)."""

    armor_class: int
    hit_points: int
    attack_bonus: int
    damage_per_round: int
    save_dc: int


def monster_stats(challenge: str) -> MonsterStats | None:
    """The DMG's statistics for a challenge rating, the middle of each range; None if unknown."""
    row = MONSTER_STATS.get(challenge_key(challenge))
    if row is None:
        return None
    armor, (low_hp, high_hp), attack, (low_damage, high_damage), save = row
    return MonsterStats(
        armor, (low_hp + high_hp) // 2, attack, (low_damage + high_damage) // 2, save
    )


def starting_hit_points(class_name: str, level: int, constitution_mod: int) -> int:
    """Hit points by the PHB: the whole hit die at level 1, then its average; CON each level."""
    die = hit_die(class_name)
    return max(1, die + constitution_mod + (level - 1) * (die // 2 + 1 + constitution_mod))


def casting_ability(class_name: str) -> str | None:
    """The ability a class casts with ("Magicien" -> "intelligence"); None for non-casters."""
    key = class_key(class_name)
    return CASTING_ABILITY.get(key) if key else None


def spell_slots_for(class_name: str, level: int) -> dict[int, int] | None:
    """Spell slots by slot level for a single-class character; None for non-casters."""
    key = class_key(class_name)
    progression = CLASSES[key][1] if key else "none"
    if progression == "full":
        return dict(enumerate(FULL_CASTER_SLOTS[level], start=1))
    if progression in ("half", "half_up"):
        if progression == "half" and level < 2:
            return {}
        return dict(enumerate(FULL_CASTER_SLOTS[(level + 1) // 2], start=1))
    if progression == "pact":
        count, slot_level = PACT_SLOTS[level]
        return {slot_level: count}
    return None


@dataclass(frozen=True)
class Difficulty:
    """An encounter rated against a party (DMG ch. 3, "Creating a Combat Encounter")."""

    total_xp: int
    multiplier: float
    adjusted_xp: int
    thresholds: tuple[int, int, int, int]  # easy, medium, hard, deadly for the party
    rating: str  # trivial, easy, medium, hard, deadly


def encounter_difficulty(party_levels: list[int], monster_xps: list[int]) -> Difficulty:
    """Rate monsters against a party: XP times a count multiplier, against thresholds."""
    if not party_levels:
        raise ValueError("the party has no characters")
    per_level = [DIFFICULTY_THRESHOLDS[min(20, max(1, level))] for level in party_levels]
    easy, medium, hard, deadly = (sum(row[i] for row in per_level) for i in range(4))
    step = _multiplier_step(len(monster_xps))
    if len(party_levels) < 3:
        step += 1
    elif len(party_levels) >= 6:
        step -= 1
    multiplier = ENCOUNTER_MULTIPLIERS[max(0, min(step, len(ENCOUNTER_MULTIPLIERS) - 1))]
    total = sum(monster_xps)
    adjusted = int(total * multiplier) if monster_xps else 0
    ratings = ((deadly, "deadly"), (hard, "hard"), (medium, "medium"), (easy, "easy"))
    rating = next((name for limit, name in ratings if adjusted >= limit), "trivial")
    return Difficulty(total, multiplier, adjusted, (easy, medium, hard, deadly), rating)


def _multiplier_step(monsters: int) -> int:
    """Index into ENCOUNTER_MULTIPLIERS for a monster count, before party size."""
    for step, upper in enumerate((0, 1, 2, 6, 10, 14)):
        if monsters <= upper:
            return step
    return 6


def ability_name(text: str | None) -> str | None:
    """ "INT", "Intelligence" or French "Sagesse" -> the ability's name."""
    if not text:
        return None
    wanted = normalize(text)[:3]
    found = next((a for a in ABILITIES if a.startswith(wanted)), None)
    return found or _FRENCH_ABILITIES.get(wanted)


def class_saves(class_name: str) -> list[str]:
    """The saving throws a class is proficient in; none for a class the rules do not know."""
    key = class_key(class_name)
    return list(CLASS_SAVES[key]) if key else []
