"""The tools test_tools.py leaves out: the world, the table's state, the log, the fight's edges."""

import pytest
from fastmcp import Client

from tests.helpers import call, call_error

pytestmark = pytest.mark.anyio


async def test_the_campaign_s_description_and_its_long_setting(client: Client) -> None:
    await call(client, "create_campaign", name="Harbor", description="Fog and bells")
    updated = await call(
        client, "update_campaign", setting="Salt. " * 400, world_notes="The bell is cursed."
    )
    assert updated == "Campaign 'Harbor' updated: setting, world_notes."
    info = await call(client, "get_campaign_info")
    assert "(900 more characters: full=true)" in info and "The bell is cursed." in info
    assert "more characters" not in await call(client, "get_campaign_info", full=True)
    assert "Nothing to change" in await call_error(client, "update_campaign")


async def test_locations_from_creation_to_listing(client: Client) -> None:
    await call(client, "create_campaign", name="Harbor", description="d")
    await call(
        client, "create_location", name="Old Lighthouse", location_type="ruin", description="Dark"
    )
    await call(client, "update_location", name_or_id="lighthouse", population=0, notes="Haunted")
    shown = await call(client, "get_location", name_or_id="old lighthouse")
    assert "Old Lighthouse" in shown and "Haunted" in shown
    assert "Old Lighthouse" in await call(client, "list_locations")


async def test_npcs_and_quests_are_read_back(client: Client) -> None:
    await call(client, "create_campaign", name="Harbor", description="d")
    await call(client, "create_npc", name="Mara")
    await call(client, "update_npc", name_or_id="mara", occupation="Innkeeper")
    assert "Innkeeper" in await call(client, "get_npc", name_or_id="Mara")
    await call(client, "create_quest", title="Ring the bell", description="At dawn")
    assert "At dawn" in await call(client, "get_quest", title_or_id="ring the bell")


async def test_the_table_s_state_and_sessions(client: Client) -> None:
    await call(client, "create_campaign", name="Harbor", description="d")
    await call(client, "create_character", name="Aria", character_class="Wizard", race="Elf")
    await call(client, "update_game_state", current_location="Docks", party_funds="12 gp")
    state = await call(client, "get_game_state")
    assert "Location: Docks." in state and "Aria (level 1) HP" in state
    assert "Aria" in await call(client, "list_characters")
    await call(client, "add_session_note", session_number=1, summary="They met at the inn.")
    assert "They met at the inn." in await call(client, "get_sessions")


async def test_items_come_and_go(client: Client) -> None:
    await call(client, "create_campaign", name="Harbor", description="d")
    await call(client, "create_character", name="Aria", character_class="Wizard", race="Elf")
    await call(
        client, "add_item_to_character", character_name_or_id="Aria", item_name="Torch", quantity=3
    )
    left = await call(
        client,
        "remove_item_from_character",
        character_name_or_id="Aria",
        item_name="torch",
        quantity=2,
    )
    assert left == "Aria has 1 x Torch left."


async def test_the_fight_s_edges(client: Client) -> None:
    await call(client, "create_campaign", name="Harbor", description="d")
    await call(client, "create_character", name="Aria", character_class="Wizard", race="Elf")
    saved = await call(client, "save_monster", name="Bog Horror", challenge_rating="2")
    assert "AC and HP come from the challenge rating" in saved
    assert "Bog Horror" in await call(client, "get_monsters")
    await call(
        client,
        "start_combat",
        participants=[{"name": "Aria", "initiative": 15}, {"name": "Bog Horror", "initiative": 5}],
    )
    joined = await call(client, "add_combatant", participant={"name": "Rat", "initiative": 10})
    assert joined.startswith("Rat joins the fight.")
    assert "has no legendary actions" in await call_error(
        client, "use_legendary", name="Bog Horror"
    )
    reacted = await call(client, "take_reaction", name="rat", reaction="opportunity attack")
    assert reacted == (
        "Rat uses its reaction (opportunity attack); it comes back at the start of its turn."
    )
    assert "used its reaction this round" in await call_error(client, "take_reaction", name="Rat")
    await call(client, "change_hit_points", names=["Aria"], amount=-6)
    await call(client, "next_turn")
    await call(client, "next_turn")
    turn = await call(client, "next_turn")  # round 2: Aria, down
    assert "Aria is down: roll a death save (d20) and call record_death_save." in turn
    saved_once = await call(
        client, "record_death_save", character_name_or_id="Aria", outcome="success"
    )
    assert saved_once == "Aria: 1 successes, 0 failures."
