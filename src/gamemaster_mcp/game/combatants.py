"""Turning participants into combatants: characters linked, monsters filled in."""

import random
import secrets
from collections import Counter
from collections.abc import Sequence
from typing import Any

from gamemaster_mcp.game import bestiary, characters, dice, registry, seating
from gamemaster_mcp.game.dice import RollResult
from gamemaster_mcp.models import Campaign, Character, Combatant, Encounter, Monster, Participant

_SYSTEM_RNG = secrets.SystemRandom()


def build(campaign: Campaign, participant: Participant) -> Combatant:
    """A combatant for *participant*.

    A party character is linked to its sheet (hit points live there). A name
    found in the bestiary takes that stat block, unless the call gives its own
    hit points or armor class. Anyone else keeps what the call gives.
    """
    name = participant.name.strip()
    character = character_for(campaign, name)
    if character is not None:
        return Combatant(
            name=character.name, initiative=participant.initiative, character_id=character.id
        )
    monster = bestiary.monster_for(campaign, name)
    hit_points = participant.hit_points or (monster.hit_points if monster else None)
    armor_class = participant.armor_class
    if armor_class is None and monster is not None:
        armor_class = monster.armor_class
    return Combatant(
        name=name,
        initiative=participant.initiative,
        monster=monster.name if monster else None,
        hit_points=hit_points,
        hit_points_max=hit_points,
        armor_class=armor_class,
        xp=monster.xp if monster else 0,
        size=monster.size if monster else "medium",
        speed=bestiary.walking_speed(monster) if monster else None,
        **(legendary(monster) if monster else {}),
    )


def legendary(monster: Monster) -> dict[str, Any]:
    """A combatant's boss fields from its stat block, its legendary uses full."""
    return {
        "boss": monster.boss,
        "legendary_actions": monster.legendary_actions,
        "legendary_actions_left": monster.legendary_actions,
        "legendary_resistances_left": monster.legendary_resistances,
    }


def character_for(campaign: Campaign, name: str) -> Character | None:
    """The party character a combatant name stands for: its name, whole words of it
    ("Aria" for "Aria Moonwhisper"), or a name that holds it ("Fizbin the gnome").
    A part of a word is not enough: a "Wolf" is not "Wolfgang"."""
    found = registry.find_exact(campaign.characters, name)
    if found is not None:
        return found
    words = f" {registry.normalize(name)} "
    holding = [
        c
        for c in campaign.characters.values()
        if f" {registry.normalize(c.name)} " in words or words in f" {registry.normalize(c.name)} "
    ]
    return holding[0] if len(holding) == 1 else None


def refresh(campaign: Campaign) -> list[str]:
    """Bring the running fight up to date with the sheets and the bestiary.

    A combatant named after a party character but not linked to its sheet is
    linked (its hit points, conditions and speed then come from the sheet); a
    monster fighting without hit points takes its stat block's, once saved.
    Returns a line per combatant changed.
    """
    lines: list[str] = []
    order = campaign.game_state.initiative_order
    linked = {c.character_id for c in order if c.character_id}
    for combatant in order:
        if combatant.character_id is not None:
            continue
        character = character_for(campaign, combatant.name)
        if character is not None and character.id not in linked:
            combatant.character_id, combatant.hit_points, combatant.hit_points_max = (
                character.id,
                None,
                None,
            )
            linked.add(character.id)
            lines.append(f"{combatant.name} now plays from {character.name}'s sheet.")
            continue
        monster = bestiary.monster_for(campaign, combatant.name)
        if monster is not None and combatant.hit_points is None:
            _take_stats(combatant, monster)
            lines.append(
                f"{combatant.name} takes the {monster.name} stat block: "
                f"HP {monster.hit_points}, AC {combatant.armor_class}."
            )
    return lines


def _take_stats(combatant: Combatant, monster: Monster) -> None:
    combatant.monster = monster.name
    combatant.hit_points = combatant.hit_points_max = monster.hit_points
    if combatant.armor_class is None:
        combatant.armor_class = monster.armor_class
    if combatant.speed is None:
        combatant.speed = bestiary.walking_speed(monster)
    combatant.xp = monster.xp
    combatant.size = monster.size
    for field, value in legendary(monster).items():
        setattr(combatant, field, value)


def from_encounter(
    campaign: Campaign, encounter: Encounter, rng: random.Random | None = None
) -> list[Combatant]:
    """The encounter's monsters, each with initiative rolled (d20 + bonus)."""
    rng = rng or _SYSTEM_RNG
    combatants: list[Combatant] = []
    for group in encounter.monsters:
        monster = bestiary.find_monster(campaign, group.monster)
        for number in range(group.count):
            combatants.append(
                Combatant(
                    name=monster.name,
                    initiative=rng.randint(1, 20) + monster.initiative_bonus,
                    monster=monster.name,
                    hit_points=monster.hit_points,
                    hit_points_max=monster.hit_points,
                    armor_class=monster.armor_class,
                    xp=monster.xp,
                    size=monster.size,
                    speed=bestiary.walking_speed(monster),
                    position=group.at[number].upper() if number < len(group.at) else None,
                    hidden=group.hidden,
                    **legendary(monster),
                )
            )
    return combatants


def party_at_the_table(campaign: Campaign) -> list[tuple[Combatant, RollResult]]:
    """The characters at the table, each with initiative rolled (d20 + Dexterity):
    for a fight started with its foes only."""
    joined: list[tuple[Combatant, RollResult]] = []
    for character in seating.present_characters(campaign):
        bonus = characters.initiative(character)
        result = dice.roll(f"d20{bonus:+d}" if bonus else "d20")
        fighter = Combatant(
            name=character.name, initiative=result.total, character_id=character.id
        )
        joined.append((fighter, result))
    return joined


def number_duplicates(order: Sequence[Combatant]) -> list[Combatant]:
    """Same-named combatants become "Goblin 1", "Goblin 2"... so they can be told apart."""
    totals = Counter(registry.normalize(c.name) for c in order)
    taken = set(totals)
    seen: Counter[str] = Counter()
    numbered: list[Combatant] = []
    for combatant in order:
        key = registry.normalize(combatant.name)
        if totals[key] > 1 and combatant.character_id is None:
            seen[key] += 1
            while f"{key} {seen[key]}" in taken:  # a "Goblin 1" given by name
                seen[key] += 1
            combatant = combatant.model_copy(update={"name": f"{combatant.name} {seen[key]}"})
        numbered.append(combatant)
    return numbered


def unique_name(taken: Sequence[Combatant], name: str) -> str:
    """*name*, or the next free "name N" when the fight already has one."""
    names = {registry.normalize(c.name) for c in taken}
    if registry.normalize(name) not in names and registry.normalize(f"{name} 1") not in names:
        return name
    number = 2
    while registry.normalize(f"{name} {number}") in names:
        number += 1
    return f"{name} {number}"
