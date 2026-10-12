"""The battle map: squares, placement, and moving by the 5e rules."""

import json

import pytest
from fastmcp import Client

from gamemaster_mcp.errors import InvalidChangeError
from gamemaster_mcp.game import battlefield, bestiary, combat, grid, movement, rules
from gamemaster_mcp.game.movement import Order
from gamemaster_mcp.models import Battlefield, Campaign, Combatant, Monster
from gamemaster_mcp.views import public, widgets
from tests.helpers import call, call_error, make_campaign, make_character


def arena(walls: tuple[str, ...] = (), difficult: tuple[str, ...] = ()) -> Campaign:
    """Aria (party, speed 30) at B2 and a goblin at F2, on a 10x6 map; Aria's turn."""
    campaign = make_campaign()
    aria = make_character("Aria")
    campaign.characters[aria.id] = aria
    state = campaign.game_state
    combat.start(
        state,
        [
            Combatant(name="Aria", initiative=20, character_id=aria.id),
            Combatant(name="Goblin", initiative=10, hit_points=7, hit_points_max=7),
        ],
    )
    battlefield.lay_out(state, 10, 6, walls, difficult)
    battlefield.place(state, state.initiative_order[0], "B2")
    battlefield.place(state, state.initiative_order[1], "F2")
    return campaign


def go(campaign: Campaign, who: str, **order: object) -> movement.Move:
    flags = {key: bool(order.pop(key, False)) for key in ("dash", "disengage", "forced")}
    return movement.move(campaign, who, Order(**order), **flags)  # type: ignore[arg-type]


def test_squares_areas_and_distances() -> None:
    field = Battlefield(width=10, height=6)
    assert grid.parse(" d 4", field) == (3, 3) and grid.name((3, 3)) == "D4"
    assert grid.area("C1:D2", field) == [(2, 0), (3, 0), (2, 1), (3, 1)]
    with pytest.raises(InvalidChangeError, match="off the map, which runs from A1 to J6"):
        grid.parse("K1", field)
    ogre = grid.footprint((4, 1), "large")
    assert grid.feet_between([(1, 1)], ogre) == 15  # diagonals count 5 ft
    assert grid.feet_between([(3, 3)], ogre) == 5


def test_the_fight_places_everyone_at_their_edge() -> None:
    campaign = make_campaign()
    state = campaign.game_state
    battlefield.lay_out(state, 8, 5, ["D1:D5"], [])
    assert state.battlefield is not None and len(state.battlefield.walls) == 5
    combat.start(
        state,
        [
            Combatant(name="Ogre", initiative=5, size="large"),
            Combatant(name="Ally", initiative=4, ally=True),
        ],
    )
    battlefield.place_the_rest(state)
    assert [c.position for c in state.initiative_order] == ["G2", "A3"]


def test_a_move_costs_5_ft_a_square_and_10_in_difficult_terrain() -> None:
    campaign = arena(difficult=("C1:C6",))
    done = go(campaign, "Aria", to="D3")
    assert (done.feet, done.left) == (15, 15)  # B2 -> C3 (difficult, 10) -> D3 (5)
    with pytest.raises(InvalidChangeError, match="20 feet of movement away; Aria has 15 left"):
        go(campaign, "Aria", to="H3")


def test_walls_are_walked_around_and_foes_block_the_way() -> None:
    campaign = arena(walls=("D1:D5",))
    done = go(campaign, "Aria", toward="Goblin")
    # Down through the gap at D6, then up: 30 ft reach E4, 10 ft short of the goblin.
    assert (done.mover.position, done.feet) == ("E4", 30) and done.short_of == ("Goblin", 10)
    assert go(arena(), "Aria", to="E2").feet == 15
    blocked = arena(walls=("A1:J1", "A3:J6"))  # a corridor on row 2
    with pytest.raises(InvalidChangeError, match="cannot get to G2"):
        go(blocked, "Aria", to="G2")


def test_leaving_a_foes_reach_provokes_unless_disengaging() -> None:
    campaign = arena()
    goblin = campaign.game_state.initiative_order[1]
    goblin.position = "C2"
    assert go(campaign, "Aria", to="A2").provoked == ["Goblin"]
    calm = arena()
    calm.game_state.initiative_order[1].position = "C2"
    assert go(calm, "Aria", to="A2", disengage=True).provoked == []


def test_a_reaction_spent_provokes_no_more_until_its_turn() -> None:
    campaign = arena()
    state = campaign.game_state
    goblin = state.initiative_order[1]
    goblin.position = "C2"
    combat.use_reaction(state, "goblin", able=True)
    assert go(campaign, "Aria", to="A2").provoked == []
    with pytest.raises(InvalidChangeError, match="used its reaction this round"):
        combat.use_reaction(state, "goblin", able=True)
    combat.next_turn(state)  # the goblin's turn: its reaction comes back
    assert not goblin.reaction_used


def test_standing_up_and_conditions_limit_movement() -> None:
    campaign = arena()
    aria = next(iter(campaign.characters.values()))
    aria.conditions = ["prone"]
    done = go(campaign, "Aria", to="C2")
    assert done.stood_up and done.left == 10 and aria.conditions == []
    aria.conditions = ["grappled"]
    with pytest.raises(InvalidChangeError, match="cannot move while grappled"):
        go(campaign, "Aria", to="B2")
    aria.conditions, aria.exhaustion = [], 2
    assert movement.speed(campaign, campaign.game_state.initiative_order[0]) == 15


def test_dash_doubles_and_a_new_turn_restores_movement() -> None:
    campaign = arena()
    state = campaign.game_state
    done = go(campaign, "Aria", toward="Goblin", dash=True)
    assert done.feet == 15 and done.mover.position == "E2"
    combat.next_turn(state)
    combat.next_turn(state)
    assert movement.movement_left(campaign, state.initiative_order[0]) == 30


def test_toward_stops_short_when_too_far_and_pushes_stop_at_walls() -> None:
    campaign = arena()
    campaign.game_state.initiative_order[1].position = "J6"
    done = go(campaign, "Aria", toward="Goblin", feet=10)
    assert done.short_of == ("Goblin", 30)  # D4 after 10 ft; J6 is 6 squares on
    pushed = arena(walls=("H1:H6",))
    shove = go(pushed, "Goblin", away_from="Aria", feet=15, forced=True)
    assert shove.mover.position == "G2" and shove.provoked == [] and shove.forced


def test_speeds_and_sizes_come_from_race_and_bestiary() -> None:
    assert [rules.base_speed(r) for r in ("Nain des collines", "Halfeline", "Elf")] == [25, 25, 30]
    ogre = Monster(name="Ogre", armor_class=11, hit_points=59, speed="40 ft.", size="large")
    assert bestiary.walking_speed(ogre) == 40


def test_players_see_the_map_without_foes_numbers() -> None:
    campaign = arena()
    seen = public.combat(campaign)["map"]
    assert seen is not None
    goblin = seen["tokens"][1]  # type: ignore[index]
    assert goblin["health"] == "unhurt" and "hp" not in goblin
    assert [2, 1] in seen["moves"]  # type: ignore[operator]
    combat.next_turn(campaign.game_state)
    assert public.combat(campaign)["map"]["moves"] == []  # type: ignore[index]
    assert widgets.combat(campaign)["map"]["tokens"][1]["hp"] == 7  # type: ignore[index]


@pytest.mark.anyio
async def test_the_map_through_the_tools(client: Client) -> None:
    await call(client, "create_campaign", name="Ghost", description="d")
    await call(client, "create_character", name="Borin", character_class="Cleric", race="Nain")
    await call(client, "save_monster", name="Ogre", armor_class=11, hit_points=59, size="large")
    laid = await call(client, "set_battlefield", width=8, height=5, walls=["D2:D4"])
    assert "Battle map A1-H5" in laid and " 2 . . . # . . . ." in laid
    await call(
        client,
        "start_combat",
        participants=[{"name": "Borin", "initiative": 15}, {"name": "Ogre", "initiative": 8}],
    )
    placed = await call(client, "place_tokens", tokens=[{"who": "Ogre", "at": "F2"}])
    assert "b Ogre (foe, large) F2" in placed
    moved = await call(client, "move_token", who="Borin", toward="Ogre")
    assert "Borin moves 20 ft, A3 to E2" in moved and "Ogre adjacent" in moved  # round the wall
    assert "Positions: Borin" in await call(client, "get_game_state")
    refused = await call_error(client, "move_token", who="Borin", to="A1")
    assert "Borin has 5 left" in refused  # a dwarf's 25 ft, 20 spent
    await call(client, "end_combat")  # the next fight lays out its own map
    assert json.loads(await call(client, "get_screen_data", view="combat"))["map"] is None


@pytest.mark.anyio
async def test_a_creature_taken_back_leaves_the_map_without_xp(client: Client) -> None:
    await call(client, "create_campaign", name="Ghost", description="d")
    await call(client, "create_character", name="Borin", character_class="Cleric", race="Nain")
    await call(client, "save_monster", name="Goblin", challenge_rating="1/4")
    await call(client, "set_battlefield", width=8, height=5)
    await call(
        client,
        "start_combat",
        participants=[
            {"name": "Borin", "initiative": 15},
            {"name": "Goblin", "initiative": 9},
            {"name": "Goblin", "initiative": 7},
        ],
    )
    taken = await call(client, "remove_combatant", name="goblin 2", reason="withdrawn")
    assert taken == "Goblin 2 withdrawn: as if it never joined, no XP. Current turn: Borin."
    seen = json.loads(await call(client, "get_screen_data", view="combat"))
    assert [t["name"] for t in seen["map"]["tokens"]] == ["Borin", "Goblin 1"]
    assert seen["defeated"] == [] and seen["xp"] == 0
    await call(client, "remove_combatant", name="goblin 1")  # defeated: it counts
    assert "(50 XP)" in await call(client, "end_combat")
