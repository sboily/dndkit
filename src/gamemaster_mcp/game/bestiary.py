"""The bestiary (saved stat blocks) and planned encounters rated against the party."""

import re
from collections.abc import Mapping, Sequence
from typing import Any

from gamemaster_mcp.errors import InvalidChangeError
from gamemaster_mcp.game import battlefield, grid, registry, rules, seating
from gamemaster_mcp.models import Battlefield, Campaign, Encounter, EncounterGroup, Monster

MONSTER_KIND = "monster"
ENCOUNTER_KIND = "encounter"
_NUMBER_SUFFIX = re.compile(r"\s+\d+$")


def find_monster(campaign: Campaign, ref: str) -> Monster:
    """The bestiary entry *ref* names."""
    return registry.find(campaign.monsters, ref, MONSTER_KIND)


def monster_for(campaign: Campaign, name: str) -> Monster | None:
    """The bestiary entry a combatant name stands for: "Goblin 2" is a Goblin."""
    found = registry.find_exact(campaign.monsters, name)
    return found or registry.find_exact(campaign.monsters, _NUMBER_SUFFIX.sub("", name))


def save_monster(campaign: Campaign, name: str, fields: Mapping[str, Any]) -> tuple[Monster, bool]:
    """Create or update a stat block; XP follows the challenge rating unless given.

    Returns the monster and whether it is new.
    """
    values = dict(fields)
    challenge = values.get("challenge_rating")
    if challenge is not None and values.get("xp") is None:
        xp = rules.xp_for_challenge(challenge)
        if xp is None:
            raise InvalidChangeError(f"Unknown challenge rating '{challenge}'; use 0-30 or 1/8.")
        values["xp"] = xp
    values = {key: value for key, value in values.items() if value is not None}
    existing = registry.find_exact(campaign.monsters, name)
    if existing is not None:
        return registry.update(campaign.monsters, existing.id, MONSTER_KIND, values), False
    _fill_from_challenge(values)
    if values.get("boss"):  # a 5e boss is usually a legendary creature
        values.setdefault("legendary_actions", 3)
        values.setdefault("legendary_resistances", 3)
    missing = [key for key in ("armor_class", "hit_points") if key not in values]
    if missing:
        known = registry.known_names(campaign.monsters.values())
        raise InvalidChangeError(
            f"A new monster needs {' and '.join(missing)}, or a challenge_rating to set them. "
            f"To change one, give its full name: {known}."
        )
    return registry.add(
        campaign.monsters, Monster(name=name.strip(), **values), MONSTER_KIND
    ), True


def _fill_from_challenge(values: dict[str, Any]) -> None:
    """What a new monster lacks, from its challenge rating (DMG ch. 9)."""
    stats = rules.monster_stats(values.get("challenge_rating") or "")
    if stats is None:
        return
    values.setdefault("armor_class", stats.armor_class)
    values.setdefault("hit_points", stats.hit_points)
    values.setdefault(
        "actions",
        f"Attack +{stats.attack_bonus}, about {stats.damage_per_round} damage a round "
        f"(split between its attacks), save DC {stats.save_dc}.",
    )


def _check_squares(
    campaign: Campaign, field: Battlefield | None, groups: Sequence[Mapping[str, Any]]
) -> None:
    """Planned squares must be on the encounter's map, off its walls, one creature each."""
    planned = [(g["monster"], square) for g in groups for square in g.get("at") or []]
    if not planned:
        return
    if field is None:
        raise InvalidChangeError("Squares need a map: give the encounter a battlefield.")
    taken = battlefield.wall_squares(field)
    for group in groups:
        if len(group.get("at") or []) > group["count"]:
            raise InvalidChangeError(f"More squares than {group['monster']} monsters.")
    for monster, square in planned:
        size = find_monster(campaign, monster).size
        held = set(grid.footprint(grid.parse(square, field), size))
        if held & taken or any(not grid.inside(s, field) for s in held):
            raise InvalidChangeError(f"{monster} cannot stand on {square.upper()}.")
        taken |= held


def walking_speed(monster: Monster) -> int | None:
    """The walking speed in a stat block's speed text ("30 ft., fly 60 ft." -> 30)."""
    match = re.match(r"\s*(\d+)", monster.speed or "")
    return int(match.group(1)) if match else None


def find_encounter(campaign: Campaign, ref: str) -> Encounter:
    """The planned encounter *ref* names."""
    return registry.find(campaign.encounters, ref, ENCOUNTER_KIND)


def plan_encounter(
    campaign: Campaign,
    name: str,
    groups: Sequence[EncounterGroup] | None,
    fields: Mapping[str, Any],
) -> tuple[Encounter, bool]:
    """Create or update an encounter; its monsters must be in the bestiary."""
    values = {key: value for key, value in fields.items() if value is not None}
    if groups is not None:
        # One error naming every unknown monster, then the bestiary's own spelling.
        registry.find_many(campaign.monsters, [g.monster for g in groups], MONSTER_KIND)
        values["monsters"] = [
            {**g.model_dump(), "monster": find_monster(campaign, g.monster).name} for g in groups
        ]
    existing = registry.find_exact(campaign.encounters, name)
    _check_squares(
        campaign,
        values.get("battlefield") or (existing.battlefield if existing else None),
        values.get("monsters") or (existing.model_dump()["monsters"] if existing else []),
    )
    if existing is not None:
        return registry.update(campaign.encounters, existing.id, ENCOUNTER_KIND, values), False
    if not values.get("monsters"):
        known = registry.known_names(campaign.encounters.values())
        raise InvalidChangeError(
            f"A new encounter needs its monsters. To change one, give its full name: {known}."
        )
    encounter = Encounter.model_validate({"name": name.strip(), **values})
    return registry.add(campaign.encounters, encounter, ENCOUNTER_KIND), True


def difficulty(campaign: Campaign, encounter: Encounter) -> rules.Difficulty | None:
    """The encounter rated against the characters at the table; None without any.

    Two players out of four make a medium fight a deadly one: absent players'
    characters do not count, once there has been a roll call (``seating``).
    """
    levels = [c.character_class.level for c in seating.present_characters(campaign)]
    if not levels:
        return None
    xps = [
        find_monster(campaign, group.monster).xp
        for group in encounter.monsters
        for _ in range(group.count)
    ]
    return rules.encounter_difficulty(levels, xps)
