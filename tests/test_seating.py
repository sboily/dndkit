"""The table: who plays which character, who is present, and what follows from it."""

from datetime import UTC, datetime

import pytest
from fastmcp import Client

from gamemaster_mcp.errors import NotFoundError
from gamemaster_mcp.game import bestiary, progression, seating
from gamemaster_mcp.models import Campaign, Encounter, EncounterGroup, Monster
from gamemaster_mcp.tools import render
from tests.helpers import call, call_error, make_campaign, make_character


def party_of_three() -> Campaign:
    campaign = make_campaign()
    for name, player in (("Élodie", "Sylvain"), ("Borin", "Marc"), ("Gareth", "Paul")):
        character = make_character(name, player_name=player)
        campaign.characters[character.id] = character
    thorin = make_character("Thorin")
    campaign.characters[thorin.id] = thorin
    return campaign


def test_without_a_roll_call_everyone_is_present() -> None:
    campaign = party_of_three()
    assert len(seating.present_characters(campaign)) == 4
    text = render.table(campaign)
    assert text.startswith("Nobody is seated yet. As soon as a player says who they are")
    assert "call seat_players with them" in text and "Sylvain plays Élodie" in text


def test_the_roll_call_seats_players_with_their_characters() -> None:
    campaign = party_of_three()
    assert seating.seat(campaign, "sylvain", None) is None  # already plays Élodie
    note = seating.seat(campaign, " Julie ", "borin")
    assert note == "Borin was played by Marc, now by Julie."
    seating.seat(campaign, "Ana", None)
    assert campaign.game_state.players_present == ["sylvain", "Julie", "Ana"]
    assert [c.name for c in seating.present_characters(campaign)] == ["Élodie", "Borin"]
    assert render.table(campaign) == (
        "At the table: sylvain plays Élodie; Julie plays Borin; Ana has no character yet. "
        "Absent: Gareth (Paul). Nobody plays Thorin."
    )


def test_players_leave_and_a_new_session_starts_over() -> None:
    campaign = party_of_three()
    seating.seat(campaign, "Sylvain", None)
    seating.seat(campaign, "Marc", None)
    seating.leave(campaign, "MARC")
    assert campaign.game_state.players_present == ["Sylvain"]
    with pytest.raises(NotFoundError, match="At the table: Sylvain"):
        seating.leave(campaign, "Paul")
    seating.clear(campaign)
    assert campaign.game_state.players_present == []


def test_experience_and_difficulty_count_the_characters_at_the_table() -> None:
    campaign = party_of_three()
    goblin = Monster(name="Goblin", armor_class=15, hit_points=7, xp=50)
    campaign.monsters[goblin.id] = goblin
    ambush = Encounter(name="Ambush", monsters=[EncounterGroup(monster="Goblin", count=2)])
    before = bestiary.difficulty(campaign, ambush)
    seating.seat(campaign, "Sylvain", None)
    after = bestiary.difficulty(campaign, ambush)
    assert before is not None and after is not None
    assert (before.rating, after.rating) == ("easy", "deadly")
    lines = progression.award_experience(campaign, [], 100)
    assert lines[0] == "100 XP split between 1: 100 each."
    progression.award_experience(campaign, ["Gareth"], 10)  # named: absent or not
    assert {c.name: c.experience_points for c in campaign.characters.values()} == {
        "Élodie": 100,
        "Borin": 0,
        "Gareth": 10,
        "Thorin": 0,
    }


@pytest.mark.anyio
async def test_seat_players_through_the_tool(client: Client) -> None:
    await call(client, "create_campaign", name="Ghost", description="d")
    await call(client, "create_character", name="Élodie", character_class="Rogue", race="Elf")
    assert (await call(client, "seat_players")).startswith("Nobody is seated yet")
    seated = await call(
        client,
        "seat_players",
        players=[{"player": "Sylvain", "character": "elodie"}, {"player": "Julie"}],
        start_over=True,
    )
    assert seated == "At the table: Sylvain plays Élodie; Julie has no character yet."
    assert "At the table: Sylvain plays Élodie" in await call(client, "get_game_state")
    assert "Player: Sylvain" in await call(client, "get_character", name_or_id="Élodie")
    left = await call(client, "seat_players", leaving=["julie"])
    assert left == "At the table: Sylvain plays Élodie."
    assert "Known characters" in await call_error(
        client, "seat_players", players=[{"player": "Marc", "character": "Borin"}]
    )


def test_last_session_s_table_asks_for_tonight_s_roll_call() -> None:
    campaign = party_of_three()
    seating.seat(campaign, "Sylvain", "Élodie")
    campaign.game_state.roll_call_at = datetime(2026, 1, 1, tzinfo=UTC)
    started = datetime(2026, 2, 1, tzinfo=UTC)  # this server's start, after it
    assert render.table(campaign, started).startswith("This was last session's table.")
    campaign.game_state.roll_call_at = datetime(2026, 2, 1, 20, tzinfo=UTC)
    assert render.table(campaign, started).startswith("At the table: Sylvain plays Élodie")
