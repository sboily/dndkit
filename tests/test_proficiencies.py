"""Skills and saving throws: names in English or French, bonuses on the sheets."""

import json

import pytest
from fastmcp import Client

from gamemaster_mcp.errors import InvalidChangeError
from gamemaster_mcp.game import characters, proficiencies, rules
from gamemaster_mcp.models import AbilityScore, CharacterClass
from tests.helpers import call, call_error, make_campaign, make_character

pytestmark = pytest.mark.anyio


def test_skills_and_saves_are_known_by_their_french_names_too() -> None:
    assert proficiencies.skills(["Discrétion", "arcanes", "Perception", "stealth"]) == [
        "Stealth",
        "Arcana",
        "Perception",
    ]
    assert proficiencies.saves(["DEX", "Sagesse", "for"]) == ["dexterity", "wisdom", "strength"]
    with pytest.raises(InvalidChangeError, match="Unknown skills: Cuisine"):
        proficiencies.skills(["Cuisine"])


async def test_a_sheet_gives_its_proficiency_bonuses(client: Client) -> None:
    await call(client, "create_campaign", name="Proficient", description="d")
    await call(
        client,
        "create_character",
        name="Aria",
        character_class="Magicienne",
        race="Elfe",
        intelligence=16,
        dexterity=14,
    )
    await call(
        client,
        "update_character",
        name_or_id="Aria",
        skills=["Arcanes", "Discrétion"],
        languages=["Elfique"],
        features=["Arcane Recovery"],
    )
    sheet = await call(client, "get_character", name_or_id="Aria")
    assert "Skills: Arcana +5, Stealth +4" in sheet
    assert "Saving throws: INT +5, WIS +2" in sheet  # the wizard's, from the class
    seen = json.loads(await call(client, "get_screen_data", view="character", name="Aria"))
    assert seen["skills"][1] == {"name": "Stealth", "bonus": 4}
    assert seen["saves"][0] == {"name": "int", "bonus": 5}
    refused = await call_error(client, "update_character", name_or_id="Aria", skills=["Cuisine"])
    assert "Skills (English or French names): Acrobatics" in refused


def test_french_classes_are_known_in_both_genders() -> None:
    names = ["Guerrière", "Magicienne", "Rôdeuse", "Sorcière", "Ensorceleuse", "Paladine"]
    assert [rules.class_key(n) for n in names] == [
        "fighter",
        "wizard",
        "ranger",
        "warlock",
        "sorcerer",
        "paladin",
    ]
    assert rules.class_saves("Roublarde") == ["dexterity", "intelligence"]


async def test_expertise_doubles_a_proficiency_and_bards_know_a_little_of_all(
    client: Client,
) -> None:
    await call(client, "create_campaign", name="Experts", description="d")
    for name, cls, level in (("Vex", "Roublarde", 1), ("Lyre", "Barde", 2)):
        await call(
            client,
            "create_character",
            **{"name": name, "character_class": cls, "race": "Humaine", "class_level": level},
            dexterity=16,
        )
    refused = await call_error(
        client, "update_character", name_or_id="Vex", expertise=["Escamotage"]
    )
    assert "Expertise doubles a proficiency, and Sleight of Hand is not among" in refused
    await call(
        client,
        "update_character",
        name_or_id="Vex",
        skills=["Discrétion", "Acrobaties"],
        expertise=["Discrétion"],
    )
    sheet = await call(client, "get_character", name_or_id="Vex")
    assert "Skills: Stealth +7, Acrobatics +5" in sheet  # DEX +3, proficiency +2 twice
    await call(client, "update_character", name_or_id="Vex", skills=["Acrobaties"])
    assert "Skills: Acrobatics +5" in await call(client, "get_character", name_or_id="Vex")
    found = await call(client, "check_campaign")
    assert "Vex: Expertise in 2 skills by its level, has 0" in found
    bard = await call(client, "get_character", name_or_id="Lyre")
    assert "Other checks: +1 (Jack of All Trades)" in bard


def test_jack_of_all_trades_adds_to_initiative() -> None:
    campaign = make_campaign()
    bard = make_character("Lyre", character_class=CharacterClass(name="Bard", level=5))
    bard.abilities = {**bard.abilities, "dexterity": AbilityScore(score=14)}
    characters.create(campaign, bard)
    assert characters.initiative(bard) == 2 + 1  # DEX +2, half of proficiency +3
    assert characters.initiative(make_character("Aria")) == 0  # a wizard: DEX only
