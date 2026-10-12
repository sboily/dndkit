"""The server's 5e numbers against the rules: SRD 5.1, and the DMG for the
encounter tables the SRD leaves out. Spot checks across each table's range."""

import pytest

from gamemaster_mcp.game import characters, concentration, proficiencies, resources, rests, rules
from gamemaster_mcp.game.tables import SKILLS
from gamemaster_mcp.models import AbilityScore, CharacterClass
from tests.helpers import make_campaign, make_character


@pytest.mark.parametrize(
    ("score", "modifier"), [(1, -5), (8, -1), (10, 0), (11, 0), (15, 2), (20, 5), (30, 10)]
)
def test_ability_modifiers(score: int, modifier: int) -> None:
    # SRD 5.1, Using Ability Scores: Ability Scores and Modifiers.
    assert AbilityScore(score=score).mod == modifier


@pytest.mark.parametrize(
    ("level", "bonus"),
    [(1, 2), (4, 2), (5, 3), (8, 3), (9, 4), (12, 4), (13, 5), (17, 6), (20, 6)],
)
def test_proficiency_bonus_by_level(level: int, bonus: int) -> None:
    # SRD 5.1, Beyond 1st Level: Character Advancement.
    assert rules.proficiency_bonus(level) == bonus


@pytest.mark.parametrize(
    ("xp", "level"),
    [(0, 1), (299, 1), (300, 2), (900, 3), (6500, 5), (85000, 11), (225000, 17), (355000, 20)],
)
def test_experience_for_each_level(xp: int, level: int) -> None:
    # SRD 5.1, Beyond 1st Level: Character Advancement.
    assert rules.level_for_xp(xp) == level


@pytest.mark.parametrize(
    ("names", "die"),
    [
        (("Barbarian", "Barbare"), 12),
        (("Fighter", "Guerrière", "Paladin", "Ranger", "Rôdeur"), 10),
        (("Bard", "Barde", "Cleric", "Clerc", "Druid", "Druide", "Monk", "Moine"), 8),
        (("Rogue", "Roublard", "Warlock", "Occultiste", "Sorcier"), 8),
        (("Sorcerer", "Ensorceleur", "Wizard", "Magicienne"), 6),
    ],
)
def test_hit_die_of_each_class_by_its_english_and_french_names(
    names: tuple[str, ...], die: int
) -> None:
    # SRD 5.1, each class's Hit Points.
    assert {name: rules.hit_die(name) for name in names} == dict.fromkeys(names, die)


@pytest.mark.parametrize(
    ("cls", "level", "con", "hp"),
    [
        ("Fighter", 1, 2, 12),  # the whole d10, then CON
        ("Fighter", 3, 2, 28),  # 12 + 2 x (6 + 2)
        ("Wizard", 1, 1, 7),
        ("Wizard", 5, 0, 22),  # 6 + 4 x 4
        ("Barbarian", 20, 0, 145),  # 12 + 19 x 7
        ("Cleric", 4, -1, 19),  # 7 + 3 x 4
    ],
)
def test_hit_points_by_level(cls: str, level: int, con: int, hp: int) -> None:
    # SRD 5.1, each class's Hit Points: the die at 1st level, then its average
    # (half the die plus one), the Constitution modifier each level.
    assert rules.starting_hit_points(cls, level, con) == hp


@pytest.mark.parametrize(
    ("level", "slots"),
    [
        (1, (2,)),
        (2, (3,)),
        (3, (4, 2)),
        (5, (4, 3, 2)),
        (11, (4, 3, 3, 3, 2, 1)),
        (17, (4, 3, 3, 3, 2, 1, 1, 1, 1)),
        (18, (4, 3, 3, 3, 3, 1, 1, 1, 1)),
        (20, (4, 3, 3, 3, 3, 2, 2, 1, 1)),
    ],
)
def test_full_caster_spell_slots(level: int, slots: tuple[int, ...]) -> None:
    # SRD 5.1, the Bard, Cleric, Druid, Sorcerer and Wizard tables.
    expected = dict(enumerate(slots, start=1))
    for cls in ("Bard", "Clerc", "Druid", "Sorcerer", "Magicien"):
        assert rules.spell_slots_for(cls, level) == expected


@pytest.mark.parametrize(
    ("level", "slots"),
    [
        (1, ()),
        (2, (2,)),
        (3, (3,)),
        (5, (4, 2)),
        (9, (4, 3, 2)),
        (13, (4, 3, 3, 1)),
        (17, (4, 3, 3, 3, 1)),
        (20, (4, 3, 3, 3, 2)),
    ],
)
def test_half_caster_spell_slots(level: int, slots: tuple[int, ...]) -> None:
    # SRD 5.1, the Paladin and Ranger tables: no spells at 1st level.
    expected = dict(enumerate(slots, start=1))
    assert rules.spell_slots_for("Paladin", level) == expected
    assert rules.spell_slots_for("Rôdeur", level) == expected


@pytest.mark.parametrize(
    ("level", "slots"),
    [(1, {1: 1}), (2, {1: 2}), (3, {2: 2}), (5, {3: 2}), (9, {5: 2}), (11, {5: 3}), (17, {5: 4})],
)
def test_warlock_pact_slots(level: int, slots: dict[int, int]) -> None:
    # SRD 5.1, the Warlock table: Spell Slots and Slot Level.
    assert rules.spell_slots_for("Warlock", level) == slots


def test_classes_without_spells_have_no_slots() -> None:
    for cls in ("Barbarian", "Guerrier", "Monk", "Rogue"):
        assert rules.spell_slots_for(cls, 5) is None


def test_casting_abilities() -> None:
    # SRD 5.1, each class's Spellcasting Ability.
    expected = {
        "Bard": "charisma",
        "Cleric": "wisdom",
        "Druid": "wisdom",
        "Paladin": "charisma",
        "Ranger": "wisdom",
        "Sorcerer": "charisma",
        "Warlock": "charisma",
        "Wizard": "intelligence",
        "Fighter": None,
    }
    assert {cls: rules.casting_ability(cls) for cls in expected} == expected


def test_class_saving_throws() -> None:
    # SRD 5.1, each class's Proficiencies: Saving Throws.
    expected = {
        "Barbarian": ["strength", "constitution"],
        "Bard": ["dexterity", "charisma"],
        "Cleric": ["wisdom", "charisma"],
        "Druid": ["intelligence", "wisdom"],
        "Fighter": ["strength", "constitution"],
        "Monk": ["strength", "dexterity"],
        "Paladin": ["wisdom", "charisma"],
        "Ranger": ["strength", "dexterity"],
        "Rogue": ["dexterity", "intelligence"],
        "Sorcerer": ["constitution", "charisma"],
        "Warlock": ["wisdom", "charisma"],
        "Wizard": ["intelligence", "wisdom"],
    }
    assert {cls: rules.class_saves(cls) for cls in expected} == expected


def test_skills_and_their_abilities() -> None:
    # SRD 5.1, Using Ability Scores: the skills of each ability.
    by_ability = {
        "strength": {"Athletics"},
        "dexterity": {"Acrobatics", "Sleight of Hand", "Stealth"},
        "intelligence": {"Arcana", "History", "Investigation", "Nature", "Religion"},
        "wisdom": {"Animal Handling", "Insight", "Medicine", "Perception", "Survival"},
        "charisma": {"Deception", "Intimidation", "Performance", "Persuasion"},
    }
    found: dict[str, set[str]] = {}
    for skill, ability in SKILLS.items():
        found.setdefault(ability, set()).add(skill)
    assert found == by_ability


@pytest.mark.parametrize(
    ("french", "skill"),
    [
        ("Acrobaties", "Acrobatics"),
        ("Arcanes", "Arcana"),
        ("Athlétisme", "Athletics"),
        ("Discrétion", "Stealth"),
        ("Dressage", "Animal Handling"),
        ("Escamotage", "Sleight of Hand"),
        ("Histoire", "History"),
        ("Médecine", "Medicine"),
        ("Perspicacité", "Insight"),
        ("Représentation", "Performance"),
        ("Survie", "Survival"),
        ("Tromperie", "Deception"),
        ("Intimidation", "Intimidation"),
        ("Religion", "Religion"),
    ],
)
def test_french_skill_names(french: str, skill: str) -> None:
    assert proficiencies.skill_name(french) == skill


@pytest.mark.parametrize(
    ("challenge", "xp"),
    [
        ("0", 10),
        ("1/8", 25),
        ("0.125", 25),
        ("1/4", 50),
        ("1/2", 100),
        ("1", 200),
        ("5", 1800),
        ("10", 5900),
        ("20", 25000),
        ("30", 155000),
    ],
)
def test_experience_by_challenge_rating(challenge: str, xp: int) -> None:
    # SRD 5.1, Monsters: Experience Points by Challenge Rating (CR 0: 0 or 10).
    assert rules.xp_for_challenge(challenge) == xp


@pytest.mark.parametrize(
    ("level", "thresholds"),
    [
        (1, (25, 50, 75, 100)),
        (2, (50, 100, 150, 200)),
        (5, (250, 500, 750, 1100)),
        (11, (800, 1600, 2400, 3600)),
        (17, (2000, 3900, 5900, 8800)),
        (20, (2800, 5700, 8500, 12700)),
    ],
)
def test_encounter_thresholds_by_character_level(
    level: int, thresholds: tuple[int, int, int, int]
) -> None:
    # DMG ch. 3, XP Thresholds by Character Level (not in the SRD).
    assert rules.encounter_difficulty([level], [10]).thresholds == thresholds


@pytest.mark.parametrize(
    ("monsters", "party", "multiplier"),
    [
        (1, 4, 1.0),
        (2, 4, 1.5),
        (3, 4, 2.0),
        (6, 4, 2.0),
        (7, 4, 2.5),
        (10, 4, 2.5),
        (11, 4, 3.0),
        (14, 4, 3.0),
        (15, 4, 4.0),
        (1, 2, 1.5),  # fewer than three characters: the next multiplier up
        (15, 2, 5.0),
        (1, 6, 0.5),  # six or more: the next one down
        (15, 6, 3.0),
    ],
)
def test_encounter_multipliers(monsters: int, party: int, multiplier: float) -> None:
    # DMG ch. 3, Encounter Multipliers and Party Size (not in the SRD).
    assert rules.encounter_difficulty([1] * party, [50] * monsters).multiplier == multiplier


def test_four_goblins_against_four_first_level_characters_is_deadly() -> None:
    rated = rules.encounter_difficulty([1] * 4, [50] * 4)
    assert (rated.total_xp, rated.adjusted_xp, rated.rating) == (200, 400, "deadly")


def test_experience_is_split_without_the_multiplier() -> None:
    # DMG ch. 3: the multiplier rates difficulty; the XP awarded is the monsters' own.
    assert rules.experience_per_character(200, 4) == 50


@pytest.mark.parametrize(
    ("race", "speed"),
    [("Nain des collines", 25), ("Halfelin", 25), ("Gnome", 25), ("Human", 30), ("Elfe", 30)],
)
def test_walking_speed_by_race(race: str, speed: int) -> None:
    # SRD 5.1, Races: Speed.
    assert rules.base_speed(race) == speed


def test_exhaustion_level_4_halves_the_hit_point_maximum() -> None:
    # SRD 5.1, Appendix PH-A: Conditions, Exhaustion.
    assert make_character(hp=21, exhaustion=3).hp_maximum == 21
    assert make_character(hp=21, exhaustion=4).hp_maximum == 10


def test_death_saving_throws() -> None:
    # SRD 5.1, Combat: Death Saving Throws.
    campaign = make_campaign()
    dying = make_character("Borin", hp=10)
    characters.create(campaign, dying)
    dying.hit_points_current = 0
    resources.record_death_save(campaign, "Borin", "nat1")
    assert dying.death_saves_failure == 2  # a 1 counts as two failures
    resources.record_death_save(campaign, "Borin", "nat20")
    assert (dying.hit_points_current, dying.death_saves_failure) == (1, 0)  # back with 1 HP


@pytest.mark.parametrize(("damage", "dead"), [(14, False), (15, True)])
def test_massive_damage_kills_outright(damage: int, dead: bool) -> None:
    # SRD 5.1, Combat: Instant Death: what is left after 0 HP equals or exceeds the maximum.
    campaign = make_campaign()
    hurt = make_character("Borin", hp=10)
    characters.create(campaign, hurt)
    hurt.hit_points_current = 5
    characters.change_hp(hurt, -damage)
    assert (hurt.death_saves_failure == 3) is dead


@pytest.mark.parametrize(
    ("level", "left", "after"), [(1, 0, "1d10"), (5, 0, "2d10"), (8, 1, "5d10")]
)
def test_a_long_rest_brings_back_half_the_hit_dice(level: int, left: int, after: str) -> None:
    # SRD 5.1, Adventuring: Long Rest: half the total, at least one.
    campaign = make_campaign()
    fighter = make_character(
        "Borin", hp=40, character_class=CharacterClass(name="Fighter", level=level)
    )
    characters.create(campaign, fighter)
    fighter.hit_dice_remaining = f"{left}d10"
    rests.rest(campaign, ["Borin"], "long")
    assert fighter.hit_dice_remaining == after


@pytest.mark.parametrize(("damage", "dc"), [(1, 10), (21, 10), (22, 11), (35, 17)])
def test_concentration_save_dc(damage: int, dc: int) -> None:
    # SRD 5.1, Spellcasting: Concentration: DC 10 or half the damage, the higher.
    holder = make_character(concentration="Bless")
    said = concentration.after_damage(holder, holder.name, damage, down=False)
    assert said is not None and f"DC {dc}" in said
