"""The bestiary (saved stat blocks) and planned encounters rated against the party."""

import re
from collections.abc import Mapping, Sequence
from typing import Any

from gamemaster_mcp.errors import InvalidChangeError
from gamemaster_mcp.game import registry, rules
from gamemaster_mcp.models import Campaign, Encounter, EncounterGroup, Monster

MONSTER_KIND = "monster"
ENCOUNTER_KIND = "encounter"
_NUMBER_SUFFIX = re.compile(r"\s+\d+$")


def find_monster(campaign: Campaign, ref: str) -> Monster:
    """The bestiary entry *ref* names."""
    return registry.find(campaign.monsters, ref, MONSTER_KIND)


def monster_for(campaign: Campaign, name: str) -> Monster | None:
    """The bestiary entry a combatant name stands for: "Goblin 2" is a Goblin."""
    found = registry.find_optional(campaign.monsters, name)
    return found or registry.find_optional(campaign.monsters, _NUMBER_SUFFIX.sub("", name))


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
    existing = registry.find_optional(campaign.monsters, name)
    if existing is not None:
        return registry.update(campaign.monsters, existing.id, MONSTER_KIND, values), False
    missing = [key for key in ("armor_class", "hit_points") if key not in values]
    if missing:
        raise InvalidChangeError(f"A new monster needs {' and '.join(missing)}.")
    return registry.add(
        campaign.monsters, Monster(name=name.strip(), **values), MONSTER_KIND
    ), True


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
            {"monster": find_monster(campaign, g.monster).name, "count": g.count} for g in groups
        ]
    existing = registry.find_optional(campaign.encounters, name)
    if existing is not None:
        return registry.update(campaign.encounters, existing.id, ENCOUNTER_KIND, values), False
    if not values.get("monsters"):
        raise InvalidChangeError("A new encounter needs its monsters.")
    encounter = Encounter.model_validate({"name": name.strip(), **values})
    return registry.add(campaign.encounters, encounter, ENCOUNTER_KIND), True


def difficulty(campaign: Campaign, encounter: Encounter) -> rules.Difficulty | None:
    """The encounter rated against the current party; None without characters."""
    levels = [c.character_class.level for c in campaign.characters.values()]
    if not levels:
        return None
    xps = [
        find_monster(campaign, group.monster).xp
        for group in encounter.monsters
        for _ in range(group.count)
    ]
    return rules.encounter_difficulty(levels, xps)
