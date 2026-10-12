"""Skills and saving throws: names in English or French, bonuses on the sheets."""

import json

import pytest
from fastmcp import Client

from gamemaster_mcp.errors import InvalidChangeError
from gamemaster_mcp.game import proficiencies, rules
from tests.helpers import call, call_error

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
