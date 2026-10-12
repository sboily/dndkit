"""Short and long rests (PHB ch. 8), and the Hit Dice spent and regained."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from gamemaster_mcp.errors import InvalidChangeError
from gamemaster_mcp.game import characters, dice, registry, rules
from gamemaster_mcp.game.dice import RollResult
from gamemaster_mcp.game.resources import reset_death_saves
from gamemaster_mcp.models import Campaign, Character, now

RestKind = Literal["short", "long"]


@dataclass(frozen=True)
class Rested:
    """What a rest did: a line per character, and the Hit Dice rolled."""

    lines: list[str]
    rolls: list[RollResult]


def rest(campaign: Campaign, refs: Sequence[str], kind: RestKind, hit_dice: int = 0) -> Rested:
    """A rest for the named characters, or everyone when *refs* is empty. On a short
    rest each spends *hit_dice* Hit Dice to heal."""
    if hit_dice and kind == "long":
        raise InvalidChangeError("Hit Dice are spent on a short rest; a long rest heals fully.")
    targets = (
        registry.find_many(campaign.characters, refs, characters.KIND)
        if refs
        else list(campaign.characters.values())
    )
    if kind == "long":
        return Rested([_long_rest(c) for c in targets], [])
    spent = [_spend(c, hit_dice) for c in targets] if hit_dice else []
    lines = [line for line, _ in spent] or [_short_rest(c) for c in targets]
    if spent:
        lines += [line for c in targets if (line := _pact_slots(c))]
    return Rested(lines, [roll for _, roll in spent])


def _long_rest(character: Character) -> str:
    """Needs at least 1 HP when the rest starts; half the Hit Dice come back."""
    if character.hit_points_current == 0:
        return f"{character.name} is at 0 HP and gains nothing from the rest"
    cls = character.character_class
    left = characters.hit_dice_left(character)
    regained = min(cls.level - left, max(1, cls.level // 2))
    character.hit_dice_remaining = f"{left + regained}d{rules.hit_die(cls.name)}"
    character.hit_points_current = character.hit_points_max
    character.temporary_hit_points = 0
    character.spell_slots_used = {}
    character.exhaustion = max(0, character.exhaustion - 1)
    reset_death_saves(character)
    character.updated_at = now()
    exhaustion = f", exhaustion {character.exhaustion}" if character.exhaustion else ""
    return (
        f"{character.name}: HP {character.hit_points_max}, spell slots restored, "
        f"Hit Dice {character.hit_dice_remaining}{exhaustion}"
    )


def _short_rest(character: Character) -> str:
    """Warlocks get their pact slots back; anyone may spend Hit Dice."""
    pact = _pact_slots(character)
    left = f"may spend Hit Dice to heal ({character.hit_dice_remaining} left: rest with hit_dice)"
    return f"{pact}; {left}" if pact else f"{character.name}: {left}"


def _pact_slots(character: Character) -> str | None:
    if rules.class_key(character.character_class.name) != "warlock":
        return None
    character.spell_slots_used = {}
    character.updated_at = now()
    return f"{character.name}: pact slots restored"


def _spend(character: Character, count: int) -> tuple[str, RollResult]:
    """Roll *count* Hit Dice; each heals its roll plus the Constitution modifier."""
    left = characters.hit_dice_left(character)
    if count > left:
        raise InvalidChangeError(f"{character.name} has {left} Hit Dice left.")
    die = rules.hit_die(character.character_class.name)
    con = character.abilities["constitution"].mod if "constitution" in character.abilities else 0
    result = dice.roll(f"{count}d{die}")
    healed = sum(max(0, face + con) for face in result.terms[0].faces)
    character.hit_dice_remaining = f"{left - count}d{die}"
    status = (
        characters.change_hp(character, healed)
        if healed
        else f"{character.name}: HP {character.hit_points_current}/{character.hit_points_max}"
    )
    return (
        f"{status}; spent {count}d{die} {list(result.terms[0].faces)} with CON {con:+d}: "
        f"+{healed} HP, {left - count} Hit Dice left",
        result,
    )
