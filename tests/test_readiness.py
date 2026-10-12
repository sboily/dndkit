"""check_campaign: what a campaign lacks before play, and nothing once it is ready."""

import pytest
from fastmcp import Client

from gamemaster_mcp.game import characters, readiness
from gamemaster_mcp.models import (
    AbilityScore,
    CharacterClass,
    Encounter,
    EncounterGroup,
    Monster,
)
from tests.helpers import call, make_campaign, make_character

pytestmark = pytest.mark.anyio


async def test_a_new_campaign_is_checked_then_ready(client: Client) -> None:
    await call(client, "create_campaign", name="Crypte", description="Une crypte.")
    await call(
        client,
        "create_character",
        **{"name": "Thrain", "character_class": "Guerrier", "race": "Nain", "class_level": 3},
        **{"player_name": "Sylvain", "strength": 16, "dexterity": 12, "constitution": 14},
    )
    await call(
        client,
        "create_character",
        **{"name": "Aria", "character_class": "Magicienne", "race": "Elfe"},
        **{"player_name": "Marie", "intelligence": 16, "dexterity": 14, "constitution": 12},
    )
    await call(client, "create_quest", title="La cloche", description="d", giver="Mara")
    found = await call(client, "check_campaign")
    rules_part, forgotten = found.split("Probably forgotten:")
    assert "Aria: has spell slots but knows no spells" in rules_part
    assert "Thrain: AC 11 is no armor; a fighter starts with chain mail" in forgotten
    assert "Thrain: INT, WIS, CHA still 10" in forgotten
    assert "quest La cloche: given by Mara, who is no NPC" in forgotten
    assert "Crypte: no location. Fix: create_location" in forgotten
    for line in (
        "Thrain: no skill proficiencies",
        "Thrain: carries nothing, not even a weapon",
        "Aria: STR, WIS, CHA still 10",
    ):
        assert line in forgotten
    await _fix_everything(client)
    ready = await call(client, "check_campaign")
    assert ready.startswith("Crypte is ready to play, 2 characters."), ready


async def _fix_everything(client: Client) -> None:
    await call(
        client,
        "update_character",
        **{"name_or_id": "Thrain", "armor_class": 16, "intelligence": 8, "wisdom": 12},
        skills=["Athlétisme", "Perception"],
    )
    await call(
        client,
        "update_character",
        **{"name_or_id": "Aria", "strength": 8, "wisdom": 13},
        skills=["Arcanes", "Histoire"],
    )
    for who, weapon in (("Thrain", "Hache d'armes"), ("Aria", "Dague")):
        await call(
            client,
            "add_item_to_character",
            character_name_or_id=who,
            item_name=weapon,
            item_type="weapon",
        )
    await call(client, "set_known_spell", character_name_or_id="Aria", spell="Bouclier", level=1)
    await call(client, "create_npc", name="Mara")
    await call(client, "create_location", name="Auberge", location_type="town", description="d")
    await call(client, "update_game_state", current_location="Auberge")


def test_hit_points_class_and_unarmored_defense_by_the_rules() -> None:
    campaign = make_campaign()
    characters.create(campaign, make_character("Aria", hp=30))  # a level 1 wizard
    barbarian = make_character("Grog", hp=15, character_class=CharacterClass(name="Barbare"))
    barbarian.abilities = {
        **barbarian.abilities,
        "dexterity": AbilityScore(score=14),
        "constitution": AbilityScore(score=16),
    }
    barbarian.armor_class = 12
    characters.create(campaign, barbarian)
    knight = make_character("Ser", hp=10, character_class=CharacterClass(name="Chevalier noir"))
    characters.create(campaign, knight)
    certain = [(f.subject, f.problem) for f in readiness.check(campaign) if f.certain]
    assert (
        "Aria",
        "30 hit points, outside what a level 1 Wizard with CON +0 can have (6 to 9); "
        "by the averages, 6",
    ) in certain
    assert ("Grog", "AC 12, below Unarmored Defense (10 + DEX + CON = 15)") in certain
    assert any(who == "Ser" and "is no 5e class" in what for who, what in certain)


def test_planned_fights_need_their_monsters_and_a_fair_size() -> None:
    campaign = make_campaign()
    characters.create(campaign, make_character("Aria", hp=6))
    ogre = Monster(name="Ogre", armor_class=11, hit_points=59, challenge_rating="2", xp=450)
    campaign.monsters[ogre.id] = ogre
    for fight in (
        Encounter(name="Ambush", monsters=[EncounterGroup(monster="Ogre", count=4)]),
        Encounter(name="Lair", monsters=[EncounterGroup(monster="Wyvern")]),
    ):
        campaign.encounters[fight.id] = fight
    found = {f.subject: f for f in readiness.check(campaign)}
    assert found["encounter Ambush"].problem == "deadly for the whole party, for a climax only"
    assert found["encounter Lair"].problem == "Wyvern not in the bestiary"
    assert found["encounter Lair"].certain
    assert found["Ogre"].problem == "no actions: its attacks and their damage"
