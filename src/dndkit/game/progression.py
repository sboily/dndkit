"""Experience and levels: awarding XP and levelling a character up (PHB ch. 1)."""

from collections.abc import Sequence

from dndkit.errors import InvalidChangeError
from dndkit.game import characters, registry, rules, seating
from dndkit.game.spellbook import describe_slots
from dndkit.models import Campaign, Character, now


def award_experience(campaign: Campaign, refs: Sequence[str], total_xp: int) -> list[str]:
    """Split *total_xp* evenly between the named characters, else those at the table.

    Without a roll call, the whole party is at the table (``seating``).
    """
    targets = (
        registry.find_many(campaign.characters, refs, characters.KIND)
        if refs
        else seating.present_characters(campaign)
    )
    if not targets:
        raise InvalidChangeError("There is no character to award experience to.")
    share = rules.experience_per_character(total_xp, len(targets))
    lines = [f"{total_xp} XP split between {len(targets)}: {share} each."]
    for character in targets:
        character.experience_points += share
        character.updated_at = now()
        line = f"{character.name}: {character.experience_points} XP"
        reachable = rules.level_for_xp(character.experience_points)
        if reachable > character.character_class.level:
            line += f", enough for level {reachable} (use level_up)"
        lines.append(line)
    return lines


def level_up(campaign: Campaign, ref: str, hit_die_roll: int | None) -> str:
    """Raise a character one level: hit points, proficiency, hit dice, spell slots.

    The hit point gain is the hit die roll (or the fixed average, half the die
    plus one) plus the Constitution modifier, at least 1.
    """
    character = characters.find(campaign, ref)
    cls = character.character_class
    if cls.level >= 20:
        raise InvalidChangeError(f"{character.name} is already level 20.")
    die = rules.hit_die(cls.name)
    if hit_die_roll is not None and not 1 <= hit_die_roll <= die:
        raise InvalidChangeError(f"A d{die} roll is between 1 and {die}.")
    roll = hit_die_roll if hit_die_roll is not None else die // 2 + 1
    con = character.abilities["constitution"].mod if "constitution" in character.abilities else 0
    gain = max(1, roll + con)
    level = cls.level + 1
    character.character_class = cls.model_copy(update={"level": level, "hit_dice": f"1d{die}"})
    character.hit_points_max += gain
    character.hit_points_current += gain
    character.proficiency_bonus = rules.proficiency_bonus(level)
    character.hit_dice_remaining = f"{min(level, characters.hit_dice_left(character) + 1)}d{die}"
    slots_note = _update_slots(character, level)
    character.updated_at = now()
    source = "rolled" if hit_die_roll is not None else "average"
    return (
        f"{character.name} reaches level {level}: +{gain} HP ({source} {roll}, CON {con:+d}), "
        f"HP {character.hit_points_current}/{character.hp_maximum}, "
        f"proficiency +{character.proficiency_bonus}{slots_note}. "
        f"Check the {cls.name} features gained at level {level}."
    )


def _update_slots(character: Character, level: int) -> str:
    slots = rules.spell_slots_for(character.character_class.name, level)
    if slots is None:
        if rules.class_key(character.character_class.name) is None:
            return "; unknown class, so spell slots are left as they were"
        return ""
    character.spell_slots_used = characters.slots_still_used(character, slots)
    character.spell_slots = dict(slots)
    return f", spell slots {describe_slots(character)}" if slots else ""
