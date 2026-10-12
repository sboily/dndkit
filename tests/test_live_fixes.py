"""A fight that drifted from the sheets and the bestiary, caught up; complete sheets."""

import json

import pytest
from fastmcp import Client

from dndkit.game import characters, combat, combatants
from dndkit.models import AbilityScore, Combatant, Participant
from tests.helpers import call, call_error, make_campaign, make_character

pytestmark = pytest.mark.anyio


async def start(client: Client, *fighters: tuple[str, int]) -> None:
    await call(
        client,
        "start_combat",
        participants=[{"name": name, "initiative": init} for name, init in fighters],
    )


async def test_a_monster_fighting_without_stats_takes_its_stat_block_once_saved(
    client: Client,
) -> None:
    await call(client, "create_campaign", name="Ash", description="d")
    await start(client, ("Serpente de Cendre", 18))
    refused = await call_error(client, "change_hit_points", names=["serpente"], amount=-10)
    assert "save its stat block with save_monster" in refused
    saved = await call(
        client, "save_monster", name="Serpente de Cendre", armor_class=13, hit_points=22
    )
    assert "Serpente de Cendre takes the Serpente de Cendre stat block: HP 22, AC 13." in saved
    hurt = await call(client, "change_hit_points", names=["serpente"], amount=-10)
    assert "Serpente de Cendre: HP 12/22" in hurt


async def test_a_combatant_named_after_a_character_joins_its_sheet(client: Client) -> None:
    await call(client, "create_campaign", name="Ash", description="d")
    await start(client, ("Fizbin", 15), ("Goblin", 9))  # no sheet yet
    made = await call(
        client,
        "create_character",
        name="Fizbin",
        character_class="Magicien",
        race="Gnome",
        intelligence=16,
        constitution=12,
    )
    assert "Fizbin now plays from Fizbin's sheet." in made
    assert "Casts with intelligence: spell attack +5, save DC 13." in made
    seen = json.loads(await call(client, "get_screen_data", view="combat"))
    assert seen["order"][0]["pc"] is True and seen["order"][0]["hp"] == 7  # d6 + 1


def test_a_decorated_name_still_finds_the_character() -> None:
    campaign = make_campaign()
    fizbin = make_character("Fizbin")
    campaign.characters[fizbin.id] = fizbin
    built = combatants.build(campaign, Participant(name="Fizbin le gnome", initiative=3))
    assert built.character_id == fizbin.id
    state = campaign.game_state
    combat.start(state, [Combatant(name="Fizbin (Sylvain)", initiative=12)])
    assert combatants.refresh(campaign) == ["Fizbin (Sylvain) now plays from Fizbin's sheet."]


def test_a_character_without_a_name_is_whose_turn_it_is() -> None:
    campaign = make_campaign()
    aria, borin = make_character("Aria"), make_character("Borin")
    campaign.characters.update({aria.id: aria, borin.id: borin})
    with pytest.raises(Exception, match="Which character\\? Characters: Aria, Borin"):
        characters.pick(campaign, None)
    combat.start(
        campaign.game_state, [Combatant(name="Borin", initiative=9, character_id=borin.id)]
    )
    assert characters.pick(campaign, None) is borin


def test_spellcasting_follows_the_class_and_its_ability() -> None:
    wizard = make_character("Fizbin")
    wizard.abilities = {**wizard.abilities, "intelligence": AbilityScore(score=16)}
    casting = characters.spellcasting(wizard)
    assert casting is not None and (casting.ability, casting.attack, casting.save_dc) == (
        "intelligence",
        5,
        13,
    )
    cleric = make_character(
        "Borin", character_class={"name": "Clerc"}, spellcasting_ability="Sagesse"
    )
    assert characters.spellcasting(cleric).ability == "wisdom"  # type: ignore[union-attr]
    assert (
        characters.spellcasting(make_character("Thrain", character_class={"name": "Guerrier"}))
        is None
    )


async def test_a_new_caster_gets_its_slots_and_the_sheet_shows_everything(client: Client) -> None:
    await call(client, "create_campaign", name="Ash", description="d")
    await call(
        client,
        "create_character",
        name="Fizbin",
        character_class="Wizard",
        race="Gnome",
        background="Sage",
        alignment="Neutral good",
        bio="A library's last apprentice.",
    )
    await call(
        client,
        "set_known_spell",
        character_name_or_id="Fizbin",
        spell="Fire Bolt",
        level=0,
        description="1d10 fire, 120 ft.",
    )
    sheet = json.loads(await call(client, "get_screen_data", view="character", name="fizbin"))
    assert sheet["slots"] == [[1, 2, 2]]
    assert sheet["casting"] == {"ability": "intelligence", "attack": 2, "dc": 10}
    assert sheet["spells"][0]["description"] == "1d10 fire, 120 ft."
    assert (sheet["background"], sheet["bio"]) == ("Sage", "A library's last apprentice.")
    assert "Initiative +0" in await call(client, "get_character")  # the only character
