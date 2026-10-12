"""Turning participants into combatants: characters linked, monsters filled in."""

import random
import secrets
from collections import Counter
from collections.abc import Sequence

from gamemaster_mcp.game import bestiary, registry
from gamemaster_mcp.models import Campaign, Combatant, Encounter, Participant

_SYSTEM_RNG = secrets.SystemRandom()


def build(campaign: Campaign, participant: Participant) -> Combatant:
    """A combatant for *participant*.

    A party character is linked to its sheet (hit points live there). A name
    found in the bestiary takes that stat block, unless the call gives its own
    hit points or armor class. Anyone else keeps what the call gives.
    """
    name = participant.name.strip()
    character = registry.find_optional(campaign.characters, name)
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
    )


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
                )
            )
    return combatants


def number_duplicates(order: Sequence[Combatant]) -> list[Combatant]:
    """Same-named combatants become "Goblin 1", "Goblin 2"... so they can be told apart."""
    totals = Counter(registry.normalize(c.name) for c in order)
    seen: Counter[str] = Counter()
    numbered: list[Combatant] = []
    for combatant in order:
        key = registry.normalize(combatant.name)
        if totals[key] > 1 and combatant.character_id is None:
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
