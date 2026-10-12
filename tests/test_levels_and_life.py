"""What a level gives a sheet, and the line between the dying and the dead."""

import pytest
from fastmcp import Client

from dndkit.errors import InvalidChangeError
from dndkit.game import characters, combat, progression, resources, rests, world
from dndkit.models import AbilityScore, CharacterClass, Combatant
from tests.helpers import call, make_campaign, make_character

pytestmark = pytest.mark.anyio


def test_a_character_made_at_level_9_has_its_level_s_numbers() -> None:
    campaign = make_campaign()
    wizard = make_character(character_class=CharacterClass(name="Magicien", level=9))
    characters.create(campaign, wizard)
    assert (wizard.proficiency_bonus, wizard.hit_dice_remaining) == (4, "9d6")
    assert wizard.character_class.hit_dice == "1d6" and wizard.spell_slots[5] == 1


def test_a_level_set_by_hand_moves_proficiency_slots_and_hit_dice() -> None:
    campaign = make_campaign()
    wizard = characters.create(campaign, make_character())
    wizard.spell_slots_used = {1: 2}
    fixed = characters.update(campaign, "Aria", {"class_level": 5}, {})
    assert (fixed.proficiency_bonus, fixed.hit_dice_remaining) == (3, "5d6")
    assert fixed.spell_slots[3] == 2 and fixed.spell_slots_used == {1: 2}


def test_a_level_up_adds_one_hit_die_not_all_of_them() -> None:
    campaign = make_campaign()
    fighter = make_character("Borin", character_class=CharacterClass(name="Fighter", level=3))
    characters.create(campaign, fighter)
    fighter.hit_dice_remaining = "1d10"  # two spent
    progression.level_up(campaign, "Borin", None)
    assert fighter.hit_dice_remaining == "2d10"


def test_healing_does_not_raise_the_dead_but_a_spell_can() -> None:
    campaign = make_campaign()
    aria = characters.create(campaign, make_character(hp=10))
    characters.change_hp(aria, -30)  # massive damage
    with pytest.raises(InvalidChangeError, match="is dead"):
        characters.change_hp(aria, 5)
    raised = characters.update(campaign, "Aria", {"hit_points_current": 1}, {})
    assert (raised.death_saves_failure, "unconscious" in raised.conditions) == (0, False)


def test_a_character_removed_mid_fight_leaves_it() -> None:
    campaign = make_campaign()
    aria = characters.create(campaign, make_character())
    state = campaign.game_state
    fighters = [
        Combatant(name="Aria", initiative=9, character_id=aria.id),
        Combatant(name="Goblin", initiative=5, hit_points=7),
    ]
    combat.start(state, fighters)
    world.remove_entity(campaign, "character", "Aria")
    assert [c.name for c in state.initiative_order] == ["Goblin"]
    assert state.current_combatant is state.initiative_order[0] and state.defeated == []


async def test_create_character_reports_a_level_5_caster_right(client: Client) -> None:
    await call(client, "create_campaign", name="Five", description="d")
    made = await call(
        client,
        "create_character",
        name="Elminster",
        character_class="Wizard",
        race="Human",
        class_level=5,
        intelligence=16,
    )
    assert "spell attack +6, save DC 14" in made


def test_hit_dice_heal_on_a_short_rest_and_half_come_back_on_a_long_one() -> None:
    campaign = make_campaign()
    fighter = make_character(
        "Borin", hp=60, character_class=CharacterClass(name="Fighter", level=5)
    )
    fighter.abilities = {"constitution": AbilityScore(score=14)}
    characters.create(campaign, fighter)
    fighter.hit_points_current = 10  # 3d10 + 6 heals 9 to 36: never past the maximum
    rested = rests.rest(campaign, ["Borin"], "short", hit_dice=3)
    faces = rested.rolls[0].terms[0].faces
    assert fighter.hit_points_current == 10 + sum(face + 2 for face in faces)
    assert fighter.hit_dice_remaining == "2d10" and "2 Hit Dice left" in rested.lines[0]
    with pytest.raises(InvalidChangeError, match="has 2 Hit Dice left"):
        rests.rest(campaign, ["Borin"], "short", hit_dice=3)
    with pytest.raises(InvalidChangeError, match="short rest"):
        rests.rest(campaign, ["Borin"], "long", hit_dice=1)
    rests.rest(campaign, ["Borin"], "long")
    assert fighter.hit_dice_remaining == "4d10"  # half of 5, rounded down: 2 back


async def test_the_rest_tool_rolls_hit_dice_on_the_tray(client: Client) -> None:
    await call(client, "create_campaign", name="Camp", description="d")
    await call(client, "create_character", name="Aria", character_class="Wizard", race="Elf")
    rested = await call(client, "rest", kind="short", hit_dice=1)
    assert "spent 1d6" in rested and "0 Hit Dice left" in rested
    assert "1d6" in await call(client, "get_screen_data", view="dice")


def test_a_stable_character_rolls_no_more_death_saves_until_hit_or_healed() -> None:
    campaign = make_campaign()
    aria = characters.create(campaign, make_character(hp=10))
    characters.change_hp(aria, -10)
    for _ in range(3):
        resources.record_death_save(campaign, "Aria", "success")
    assert aria.stable
    with pytest.raises(InvalidChangeError, match="is stable"):
        resources.record_death_save(campaign, "Aria", "failure")
    hit = characters.change_hp(aria, -2)
    assert "1/3 death save failures (a critical hit counts two" in hit and not aria.stable
    assert "stable at 0 HP" in resources.record_death_save(campaign, "Aria", "stabilized")
    characters.change_hp(aria, 4)
    assert (aria.stable, aria.hit_points_current) == (False, 4)


def test_exhaustion_halves_hit_points_at_4_and_kills_at_6() -> None:
    campaign = make_campaign()
    aria = characters.create(campaign, make_character(hp=21))
    tired = characters.update(campaign, "Aria", {"exhaustion": 4}, {})
    assert (tired.hp_maximum, tired.hit_points_current) == (10, 10)
    assert characters.change_hp(tired, 50) == "Aria: HP 10/10"
    rests.rest(campaign, ["Aria"], "long")  # exhaustion 3: the maximum is whole again
    assert (tired.exhaustion, tired.hit_points_current) == (3, 21)
    spent = characters.update(campaign, "Aria", {"exhaustion": 6}, {})
    assert (spent.hit_points_current, spent.death_saves_failure) == (0, 3)
    assert aria.id == spent.id
