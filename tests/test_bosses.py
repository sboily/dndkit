"""Monsters the game master invents, bosses and their legendary actions, sensible sheets."""

import pytest
from fastmcp import Client

from gamemaster_mcp.errors import InvalidChangeError
from gamemaster_mcp.game import bestiary, combat, combatants, rules
from gamemaster_mcp.models import Combatant, Participant
from tests.helpers import call, call_error, make_campaign


def test_a_challenge_rating_alone_gives_the_dmg_statistics() -> None:
    campaign = make_campaign()
    serpent, created = bestiary.save_monster(
        campaign, "Serpente de Cendre", {"challenge_rating": "5", "boss": True}
    )
    assert created and (serpent.armor_class, serpent.hit_points, serpent.xp) == (15, 138, 1800)
    assert serpent.actions.startswith("Attack +6, about 35 damage a round")
    assert (serpent.legendary_actions, serpent.legendary_resistances) == (3, 3)
    guard, _ = bestiary.save_monster(campaign, "Garde", {"challenge_rating": "1/4"})
    assert (guard.boss, guard.legendary_actions, guard.hit_points) == (False, 0, 42)
    with pytest.raises(InvalidChangeError, match="or a challenge_rating"):
        bestiary.save_monster(campaign, "Ombre", {})


def test_legendary_actions_come_back_at_the_creatures_turn() -> None:
    campaign = make_campaign()
    bestiary.save_monster(campaign, "Dragon", {"challenge_rating": "10", "boss": True})
    state = campaign.game_state
    dragon = combatants.build(campaign, Participant(name="Dragon", initiative=5))
    assert dragon.boss and dragon.legendary_actions_left == 3
    combat.start(state, [Combatant(name="Hero", initiative=20), dragon])
    combat.use_legendary(state, "dragon", resistance=False, cost=2)
    with pytest.raises(InvalidChangeError, match="1 legendary action"):
        combat.use_legendary(state, "dragon", resistance=False, cost=2)
    combat.use_legendary(state, "dragon", resistance=True, cost=1)
    combat.next_turn(state)  # the dragon's turn: its actions are back
    assert state.initiative_order[1].legendary_actions_left == 3
    with pytest.raises(InvalidChangeError, match="end of another creature's turn"):
        combat.use_legendary(state, "dragon", resistance=False, cost=1)
    assert state.initiative_order[1].legendary_resistances_left == 2  # a day's worth


def test_starting_hit_points_follow_the_class() -> None:
    assert rules.starting_hit_points("Magicien", 1, 1) == 7  # d6 + 1
    assert rules.starting_hit_points("Fighter", 3, 2) == 28  # 10 + 2, then 2 x (6 + 2)


@pytest.mark.anyio
async def test_a_boss_fight_through_the_tools(client: Client) -> None:
    await call(client, "create_campaign", name="Forge", description="d")
    made = await call(
        client,
        "create_character",
        name="Thrain",
        character_class="Guerrier",
        race="Nain",
        constitution=14,
        dexterity=12,
    )
    assert "HP 12/12, AC 11" in made  # d10 + 2, 10 + 1
    saved = await call(
        client,
        "save_monster",
        name="Gardien de Magma",
        challenge_rating="5",
        boss=True,
        size="large",
    )
    assert "Gardien de Magma (boss): AC 15, HP 138" in saved
    assert "Legendary: 3 actions a round, 3 resistances a day." in saved
    await call(
        client,
        "start_combat",
        participants=[
            {"name": "Thrain", "initiative": 15},
            {"name": "Gardien de Magma", "initiative": 9},
        ],
    )
    used = await call(client, "use_legendary", name="gardien")  # part of the name, as spoken
    assert used == "Gardien de Magma takes a legendary action; 2 left until its turn."
    state = await call(client, "get_game_state")
    assert "boss; legendary actions 2/3, resistances 3" in state
    assert "no legendary resistance" in await call_error(
        client, "use_legendary", name="Thrain", resistance=True
    )
