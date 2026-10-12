"""Concentration: one spell held, a save when hurt, lost when down or incapacitated."""

import json

import pytest
from fastmcp import Client

from gamemaster_mcp.game import characters, combat, effects
from gamemaster_mcp.models import AbilityScore, CharacterClass, Combatant
from tests.helpers import call, make_campaign, make_character

pytestmark = pytest.mark.anyio


def test_damage_asks_for_the_save_and_zero_hit_points_end_the_spell() -> None:
    campaign = make_campaign()
    cleric = make_character("Mira", hp=20, character_class=CharacterClass(name="Clerc"))
    cleric.abilities = {"constitution": AbilityScore(score=14)}
    characters.create(campaign, cleric)
    assert effects.set_concentration(campaign, "mira", "Bless") == "Mira concentrates on Bless."
    assert "(Bless ends)" in effects.set_concentration(campaign, "Mira", "Shield of Faith")
    hurt = effects.change_hit_points(campaign, ["Mira"], -24)[-1]
    assert hurt == "Mira loses concentration on Shield of Faith."  # down at 0 HP
    effects.change_hit_points(campaign, ["Mira"], 20)  # conscious again
    effects.set_concentration(campaign, "Mira", "Bless")
    asked = effects.change_hit_points(campaign, ["Mira"], -12)[-1]
    assert asked == (
        "Mira is concentrating on Bless: Constitution save DC 10, CON save +2. "
        "If it fails, set_concentration without a spell."
    )  # a cleric's saves are WIS and CHA: no proficiency in CON
    effects.change_hit_points(campaign, ["Mira"], 5)  # healing asks for nothing
    assert effects.set_condition(campaign, ["Mira"], "stunned", True)[-1] == (
        "Mira loses concentration on Bless."
    )


def test_a_monster_concentrates_too() -> None:
    campaign = make_campaign()
    shaman = Combatant(name="Shaman", initiative=10, hit_points=30, hit_points_max=30)
    combat.start(campaign.game_state, [shaman])
    effects.set_concentration(campaign, "shaman", "Hold Person")
    line = effects.change_hit_points(campaign, ["Shaman"], -24)[-1]
    assert line.startswith("Shaman is concentrating on Hold Person: Constitution save DC 12.")
    assert effects.set_concentration(campaign, "Shaman", None) == (
        "Shaman stops concentrating on Hold Person."
    )


async def test_the_screens_show_the_spell_held(client: Client) -> None:
    await call(client, "create_campaign", name="Held", description="d")
    await call(client, "create_character", name="Aria", character_class="Wizard", race="Elf")
    said = await call(client, "set_concentration", name="Aria", spell="Invisibility")
    assert said == "Aria concentrates on Invisibility."
    party = json.loads(await call(client, "get_screen_data", view="party"))
    assert party["characters"][0]["concentration"] == "Invisibility"
    sheet = await call(client, "get_character", name_or_id="Aria")
    assert "Concentrating on Invisibility." in sheet


async def test_a_timed_condition_ends_by_itself_at_the_end_of_its_turn(client: Client) -> None:
    await call(client, "create_campaign", name="Timed", description="d")
    await call(client, "create_character", name="Aria", character_class="Wizard", race="Elf")
    await call(
        client,
        "start_combat",
        participants=[{"name": "Aria", "initiative": 15}, {"name": "Ogre", "initiative": 5}],
    )
    said = await call(client, "set_condition", names=["Ogre"], condition="stunned", rounds=2)
    assert said == "Ogre: stunned (2 turns left)"
    await call(client, "set_condition", names=["Ogre"], condition="prone")
    turn = await call(client, "next_turn")  # Aria's turn ends: the ogre's timer waits
    assert "Ogre's turn" in turn and "stunned (2 turns left), prone" in turn
    await call(client, "next_turn")  # the ogre's first turn ends
    turn = await call(client, "next_turn")
    assert "Ogre: stunned ends." not in turn
    turn = await call(client, "next_turn")  # its second turn ends
    assert turn.startswith("Ogre: stunned ends.\nRound 3 begins. Aria's turn")
    seen = json.loads(await call(client, "get_screen_data", view="combat"))
    assert seen["order"][1]["conditions"] == ["prone"] and seen["order"][1]["rounds"] == {}
