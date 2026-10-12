"""5e rules tables, bestiary, monsters in combat, conditions, levels and spells."""

import random

import pytest

from dndkit.errors import InvalidChangeError, NotFoundError
from dndkit.game import (
    bestiary,
    characters,
    combat,
    combatants,
    effects,
    progression,
    reference,
    registry,
    rules,
    spellbook,
    world,
)
from dndkit.models import EncounterGroup, Participant, Quest
from tests.helpers import make_campaign, make_character


def test_spell_slots_follow_the_class_tables() -> None:
    assert rules.spell_slots_for("Magicien", 5) == {1: 4, 2: 3, 3: 2}
    assert rules.spell_slots_for("paladin", 1) == {}
    assert rules.spell_slots_for("ranger", 5) == {1: 4, 2: 2}
    assert rules.spell_slots_for("Occultiste", 11) == {5: 3}
    assert rules.spell_slots_for("fighter", 3) is None
    assert rules.class_key("Rôdeur") == "ranger" and rules.class_key("Homebrew") is None


def test_levels_and_challenge_ratings() -> None:
    assert [rules.level_for_xp(xp) for xp in (0, 299, 300, 400_000)] == [1, 1, 2, 20]
    assert [rules.proficiency_bonus(level) for level in (1, 5, 9, 17)] == [2, 3, 4, 6]
    assert rules.xp_for_challenge("0.25") == rules.xp_for_challenge("1/4") == 50
    assert rules.xp_for_challenge("31") is None


def test_encounter_difficulty_uses_the_dmg_multipliers() -> None:
    four_level_2 = rules.encounter_difficulty([2, 2, 2, 2], [50, 50, 50, 200])
    assert (four_level_2.multiplier, four_level_2.adjusted_xp, four_level_2.rating) == (
        2.0,
        700,
        "hard",
    )
    small_party = rules.encounter_difficulty([1, 1], [50])
    assert (small_party.multiplier, small_party.rating) == (1.5, "easy")
    big_party = rules.encounter_difficulty([1] * 6, [100])
    assert big_party.multiplier == 0.5


def test_unique_partial_names_are_found() -> None:
    campaign = make_campaign()
    world.create_quest(campaign, Quest(title="Le phare éteint", description="d"))
    world.create_quest(campaign, Quest(title="Le phare rouge", description="d"))
    assert registry.find(campaign.quests, "eteint", "quest").title == "Le phare éteint"
    with pytest.raises(NotFoundError):
        registry.find(campaign.quests, "phare", "quest")  # two match: ambiguous


def test_bestiary_fills_combatants_and_counts_xp() -> None:
    campaign = make_campaign()
    characters.create(campaign, make_character("Aria", hp=10))
    bestiary.save_monster(
        campaign, "Goblin", {"armor_class": 15, "hit_points": 7, "challenge_rating": "1/4"}
    )
    encounter, _ = bestiary.plan_encounter(
        campaign, "Ambush", [EncounterGroup(monster="goblin", count=2)], {}
    )
    fighters = [combatants.build(campaign, Participant(name="aria", initiative=12))]
    fighters += combatants.from_encounter(campaign, encounter, random.Random(3))
    combat.start(campaign.game_state, fighters)
    names = sorted(c.name for c in campaign.game_state.initiative_order)
    assert names == ["Aria", "Goblin 1", "Goblin 2"]
    goblin = combat.find(campaign.game_state, "goblin 1")
    assert (goblin.hit_points, goblin.armor_class, goblin.xp) == (7, 15, 50)
    lines = effects.change_hit_points(campaign, ["Goblin 1", "Aria"], -8)
    assert "leaves the fight" in lines[0] and "HP 2/10" in lines[1]
    summary = combat.end(campaign.game_state)
    assert ([c.name for c in summary.defeated], summary.xp) == (["Goblin 1"], 50)


def test_newcomers_keep_the_current_turn() -> None:
    campaign = make_campaign()
    state = campaign.game_state
    combat.start(state, [combatants.build(campaign, Participant(name="Orc", initiative=10))])
    combat.add(state, combatants.build(campaign, Participant(name="Orc", initiative=20)))
    assert [c.name for c in state.initiative_order] == ["Orc 2", "Orc"]
    assert state.current_combatant is not None and state.current_combatant.name == "Orc"


def test_untracked_monster_hit_points_are_refused() -> None:
    campaign = make_campaign()
    combat.start(
        campaign.game_state, [combatants.build(campaign, Participant(name="Shade", initiative=5))]
    )
    with pytest.raises(InvalidChangeError, match="not tracked"):
        effects.change_hit_points(campaign, ["Shade"], -3)


def test_conditions_on_characters_and_monsters() -> None:
    campaign = make_campaign()
    aria = characters.create(campaign, make_character("Aria"))
    combat.start(
        campaign.game_state,
        [combatants.build(campaign, Participant(name="Wolf", initiative=5, hit_points=11))],
    )
    effects.set_condition(campaign, ["Aria", "Wolf"], "prone", True)
    assert aria.conditions == ["prone"]
    assert combat.find(campaign.game_state, "wolf").conditions == ["prone"]
    effects.set_condition(campaign, ["Aria"], "prone", False)
    assert aria.conditions == []


def test_temporary_hit_points_do_not_stack() -> None:
    campaign = make_campaign()
    aria = characters.create(campaign, make_character("Aria"))
    effects.grant_temporary_hp(campaign, ["Aria"], 5)
    effects.grant_temporary_hp(campaign, ["Aria"], 3)
    assert aria.temporary_hit_points == 5


def test_experience_and_level_up() -> None:
    campaign = make_campaign()
    wizard = characters.create(
        campaign, make_character("Aria", hp=8, character_class={"name": "Magicien", "level": 1})
    )
    lines = progression.award_experience(campaign, [], 600)
    assert "enough for level 2" in lines[1]
    text = progression.level_up(campaign, "Aria", 4)
    assert (wizard.character_class.level, wizard.hit_points_max) == (2, 12)
    assert wizard.spell_slots == {1: 3} and "spell slots" in text
    with pytest.raises(InvalidChangeError, match="between 1 and 6"):
        progression.level_up(campaign, "Aria", 9)


def test_known_spells_are_added_changed_and_forgotten() -> None:
    campaign = make_campaign()
    aria = characters.create(campaign, make_character("Aria"))
    with pytest.raises(InvalidChangeError, match="give its level"):
        spellbook.set_known_spell(campaign, "Aria", "Shield", {})
    spellbook.set_known_spell(campaign, "Aria", "Shield", {"level": 1})
    _, spell, created = spellbook.set_known_spell(campaign, "Aria", "shield", {"prepared": True})
    assert not created and spell.prepared
    spellbook.forget_spell(campaign, "Aria", "Shield")
    assert aria.spells_known == []


def test_rules_reference_in_english_and_french() -> None:
    assert reference.lookup("à terre")[0] == "prone"
    assert reference.lookup("Jets contre la mort")[0] == "death saves"
    with pytest.raises(NotFoundError, match="Topics:"):
        reference.lookup("dragon breath")
