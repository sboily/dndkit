"""What a campaign still lacks before it is played, by the 5e rules (SRD 5.1).

The checks read the campaign and say what is wrong or missing, each with the
tool that fixes it. They change nothing: a game master may keep a fighter
without armor on purpose. ``certain`` findings break a rule; the others are
what a first campaign usually forgets.
"""

from collections.abc import Callable
from dataclasses import dataclass

from dndkit.game import bestiary, registry, rules
from dndkit.models import ABILITIES, Campaign, Character, Encounter

# The armor in each class's starting equipment, for a sheet still at 10 + DEX.
STARTING_ARMOR = {
    "artificer": "studded leather (AC 12 + DEX) or scale mail (14 + DEX, max 2)",
    "bard": "leather armor (AC 11 + DEX)",
    "cleric": "scale mail and a shield (AC 16 + DEX, max 2)",
    "druid": "leather armor and a wooden shield (AC 13 + DEX)",
    "fighter": "chain mail (AC 16, 18 with a shield)",
    "paladin": "chain mail (AC 16, 18 with a shield)",
    "ranger": "scale mail (AC 14 + DEX, max 2) or leather (11 + DEX)",
    "rogue": "leather armor (AC 11 + DEX)",
    "warlock": "leather armor (AC 11 + DEX)",
}
# Unarmored Defense: AC 10 + DEX + this ability's modifier.
UNARMORED_DEFENSE = {"barbarian": "constitution", "monk": "wisdom"}
STANDARD_ARRAY = "15, 14, 13, 12, 10, 8"
# Hit points a feature may add per level (Tough, a hill dwarf's toughness).
EXTRA_HP_PER_LEVEL = 3
# Expertise in two skills at each of these class levels.
EXPERTISE_LEVELS = {"rogue": (1, 6), "bard": (3, 10)}


@dataclass(frozen=True)
class Finding:
    subject: str  # a character, a quest, a monster, or the campaign
    problem: str
    fix: str  # the call that fixes it
    certain: bool  # breaks a rule, rather than likely forgotten


def check(campaign: Campaign) -> list[Finding]:
    """Everything worth fixing before play: the campaign, each character, the bestiary."""
    found = _world(campaign)
    for character in campaign.characters.values():
        found += [f for check in CHARACTER_CHECKS if (f := check(character))]
    return found + _bestiary(campaign)


def _world(campaign: Campaign) -> list[Finding]:
    name = campaign.name
    found: list[Finding] = []
    if not campaign.characters:
        found.append(Finding(name, "no characters", "create_character for each player", True))
    if not any(q.status == "active" for q in campaign.quests.values()):
        found.append(Finding(name, "no active quest: the story's hook", "create_quest", False))
    if not campaign.npcs:
        found.append(Finding(name, "no NPC to meet first", "create_npc", False))
    found += _whereabouts(campaign)
    for quest in campaign.quests.values():
        if quest.giver and not registry.find_exact(campaign.npcs, quest.giver):
            problem = f"given by {quest.giver}, who is no NPC"
            found.append(Finding(f"quest {quest.title}", problem, "create_npc", False))
    return found


def _whereabouts(campaign: Campaign) -> list[Finding]:
    here = campaign.game_state.current_location
    if here and registry.find_exact(campaign.locations, here):
        return []
    if here:
        problem, fix = f"the party is at {here}, which is no location", f"create_location {here}"
    elif campaign.locations:
        problem, fix = "the party is nowhere", "update_game_state current_location"
    else:
        problem, fix = "no location", "create_location, then update_game_state current_location"
    return [Finding(campaign.name, problem, fix, False)]


def _class(c: Character) -> Finding | None:
    if rules.class_key(c.character_class.name):
        return None
    problem = (
        f"{c.character_class.name} is no 5e class: its hit dice, saves and spells are guesses"
    )
    fix = "remove_from_campaign, then create_character with a class from the book"
    return Finding(c.name, problem, fix, True)


def _armor(c: Character) -> Finding | None:
    key = rules.class_key(c.character_class.name) or ""
    unarmored = 10 + c.abilities["dexterity"].mod
    if key in UNARMORED_DEFENSE:
        ability = UNARMORED_DEFENSE[key]
        least = unarmored + c.abilities[ability].mod
        if c.armor_class < least:
            short = ability[:3].upper()
            problem = f"AC {c.armor_class}, below Unarmored Defense (10 + DEX + {short} = {least})"
            return Finding(c.name, problem, "update_character armor_class", True)
    elif key in STARTING_ARMOR and c.armor_class <= unarmored:
        problem = f"AC {c.armor_class} is no armor; a {key} starts with {STARTING_ARMOR[key]}"
        return Finding(c.name, problem, "update_character armor_class", False)
    return None


def _abilities(c: Character) -> Finding | None:
    unset = [a[:3].upper() for a in ABILITIES if c.abilities[a].score == 10]
    if len(unset) < 3:
        return None
    problem = f"{', '.join(unset)} still 10, as if never set (standard array {STANDARD_ARRAY})"
    return Finding(c.name, problem, "update_character with the scores", False)


def _hit_points(c: Character) -> Finding | None:
    """Within what the hit dice allow: the whole die at level 1, then 1 to the die."""
    cls = c.character_class
    if not rules.class_key(cls.name):
        return None
    die, con, level = rules.hit_die(cls.name), c.abilities["constitution"].mod, cls.level
    least = max(1, die + con) + (level - 1) * max(1, 1 + con)
    most = level * (die + con + EXTRA_HP_PER_LEVEL)
    if least <= c.hit_points_max <= most:
        return None
    average = rules.starting_hit_points(cls.name, level, con)
    problem = (
        f"{c.hit_points_max} hit points, outside what a level {level} {cls.name} with CON "
        f"{con:+d} can have ({least} to {most}); by the averages, {average}"
    )
    return Finding(c.name, problem, "update_character hit_points_max", True)


def _expertise(c: Character) -> Finding | None:
    """A rogue's or a bard's Expertise (or thieves' tools for a rogue, hence not certain)."""
    levels = EXPERTISE_LEVELS.get(rules.class_key(c.character_class.name) or "", ())
    due = 2 * sum(c.character_class.level >= level for level in levels)
    if len(c.skill_expertise) >= due:
        return None
    problem = f"Expertise in {due} skills by its level, has {len(c.skill_expertise)}"
    return Finding(c.name, problem, "update_character expertise", False)


def _gear(c: Character) -> Finding | None:
    items = [*c.inventory, *(i for i in c.equipment.values() if i)]
    if not items:
        problem = "carries nothing, not even a weapon or a pack"
    elif not any(i.item_type == "weapon" for i in items):
        problem = "carries no weapon"
    else:
        return None
    return Finding(c.name, problem, "add_item_to_character with its item_type", False)


def _spells(c: Character) -> Finding | None:
    if not any(c.spell_slots.values()) or c.spells_known:
        return None
    problem = "has spell slots but knows no spells, not even a cantrip"
    return Finding(c.name, problem, "set_known_spell for each", True)


def _skills(c: Character) -> Finding | None:
    if c.skill_proficiencies:
        return None
    problem = "no skill proficiencies (2 to 4 from the class, 2 from the background)"
    return Finding(c.name, problem, "update_character skills", False)


def _player(c: Character) -> Finding | None:
    if c.player_name:
        return None
    problem = "no player: the roll call cannot seat it"
    return Finding(c.name, problem, "update_character player_name", False)


CHARACTER_CHECKS: tuple[Callable[[Character], Finding | None], ...] = (
    _class,
    _player,
    _abilities,
    _hit_points,
    _armor,
    _skills,
    _expertise,
    _gear,
    _spells,
)


def _bestiary(campaign: Campaign) -> list[Finding]:
    found = [
        Finding(m.name, "no actions: its attacks and their damage", "save_monster actions", False)
        for m in campaign.monsters.values()
        if not m.actions.strip()
    ]
    levels = [c.character_class.level for c in campaign.characters.values()]
    planned = [e for e in campaign.encounters.values() if e.status == "planned"]
    return found + [f for e in planned if (f := _encounter(campaign, e, levels))]


def _encounter(campaign: Campaign, encounter: Encounter, levels: list[int]) -> Finding | None:
    """A planned fight whose monsters are missing, or rated deadly or trivial for the party."""
    subject = f"encounter {encounter.name}"
    monsters = [(g, bestiary.monster_for(campaign, g.monster)) for g in encounter.monsters]
    missing = [g.monster for g, m in monsters if m is None]
    if missing:
        return Finding(subject, f"{', '.join(missing)} not in the bestiary", "save_monster", True)
    if not levels:
        return None
    xps = [m.xp for g, m in monsters if m for _ in range(g.count)]
    rated = rules.encounter_difficulty(levels, xps).rating
    if rated not in ("deadly", "trivial"):
        return None
    problem = f"{rated} for the whole party" + (", for a climax only" if rated == "deadly" else "")
    return Finding(subject, problem, "plan_encounter with another count", False)
