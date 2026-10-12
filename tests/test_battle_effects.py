"""The battle map, phase 2: areas of effect, cover, hidden foes, prepared maps."""

import json

import pytest
from fastmcp import Client

from gamemaster_mcp.errors import InvalidChangeError
from gamemaster_mcp.game import areas, battlefield, combat, grid, sight
from gamemaster_mcp.game.areas import Aim
from gamemaster_mcp.models import Campaign, Combatant
from gamemaster_mcp.views import everyone, public, widgets
from tests.helpers import call, call_error, make_campaign, make_character


def scene(walls: tuple[str, ...] = ()) -> Campaign:
    """Aria at B5, a goblin at H5 and an orc at J3 on a 12x9 map; Aria's turn."""
    campaign = make_campaign()
    aria = make_character("Aria")
    campaign.characters[aria.id] = aria
    state = campaign.game_state
    combat.start(
        state,
        [
            Combatant(name="Aria", initiative=20, character_id=aria.id),
            Combatant(name="Goblin", initiative=10, hit_points=7, hit_points_max=7),
            Combatant(name="Orc", initiative=5, hit_points=15, hit_points_max=15),
        ],
    )
    battlefield.lay_out(state, 12, 9, walls, [])
    for combatant, square in zip(state.initiative_order, ["B5", "H5", "J3"], strict=True):
        battlefield.place(state, combatant, square)
    return campaign


def names(area: areas.Area) -> list[str]:
    return [c.name for c in area.caught]


def test_a_sphere_holds_what_is_within_its_radius_as_the_grid_counts() -> None:
    campaign = scene()
    burst = areas.resolve(campaign.game_state, Aim("sphere", 10, at="Goblin"))
    assert len(burst.squares) == 25 and names(burst) == ["Goblin", "Orc"]
    assert campaign.game_state.battlefield is not None
    assert campaign.game_state.battlefield.area_label == "10-ft sphere"
    combat.next_turn(campaign.game_state)
    assert campaign.game_state.battlefield.area == []  # gone at the next turn


def test_walls_stop_an_area() -> None:
    campaign = scene(walls=("F3:F7",))
    burst = areas.resolve(campaign.game_state, Aim("sphere", 20, at="D5"))
    held = set(burst.squares)
    assert grid.parse("E5", campaign.game_state.battlefield) in held  # type: ignore[arg-type]
    assert grid.parse("G5", campaign.game_state.battlefield) not in held  # type: ignore[arg-type]
    assert names(burst) == ["Aria"]


def test_cones_lines_and_cubes_start_from_their_caster() -> None:
    campaign = scene()
    state = campaign.game_state
    cone = areas.resolve(state, Aim("cone", 15, source="Aria", toward="Goblin"))
    assert sorted(grid.name(s) for s in cone.squares) == ["C5", "D5", "E4", "E5", "E6"]
    bolt = areas.resolve(state, Aim("line", 60, source="Aria", toward="Goblin"))
    assert len(bolt.squares) == 10 and names(bolt) == ["Goblin"]  # never the caster
    wave = areas.resolve(state, Aim("cube", 15, source="Aria", toward="Goblin"))
    assert sorted(grid.name(s) for s in wave.squares)[:3] == ["C4", "C5", "C6"]
    with pytest.raises(InvalidChangeError, match="needs at"):
        areas.resolve(state, Aim("sphere", 20))


@pytest.mark.parametrize(
    ("walls", "cover"),
    [((), "none"), (("E5",), "half"), (("E4:E6",), "total"), (("E1:E9",), "total")],
)
def test_cover_follows_the_dmg_corner_rule(walls: tuple[str, ...], cover: str) -> None:
    state = scene(walls).game_state
    assert sight.cover(state, state.initiative_order[0], state.initiative_order[1]) == cover


def test_a_creature_in_the_way_gives_half_cover_and_an_adjacent_foe_presses() -> None:
    campaign = scene()
    state = campaign.game_state
    state.initiative_order[2].position = "E5"
    seen = sight.look(campaign, "Aria", "Goblin")
    assert (seen.feet, seen.cover, seen.in_reach) == (30, "half", False)
    state.initiative_order[2].position = "C5"
    assert sight.look(campaign, "Aria", "Goblin").pressed_by == ["Orc"]


def test_hidden_foes_stay_off_the_players_screens() -> None:
    campaign = scene()
    state = campaign.game_state
    state.initiative_order[1].hidden = True
    seen = public.combat(campaign)
    assert [f["name"] for f in seen["order"]] == ["Aria", "Orc"]
    tokens = seen["map"]["tokens"]  # type: ignore[index]
    assert [t["name"] for t in tokens] == ["Aria", "Orc"]
    assert [6, 4] in seen["map"]["moves"]  # type: ignore[index]  # no hole where it hides
    assert widgets.combat(campaign)["map"]["tokens"][1]["hidden"] is True  # type: ignore[index]
    combat.next_turn(state)
    assert everyone.party(campaign)["current"] is None  # its turn names no one


@pytest.mark.anyio
async def test_a_prepared_ambush_through_the_tools(client: Client) -> None:
    await call(client, "create_campaign", name="Ghost", description="d")
    await call(client, "create_character", name="Borin", character_class="Cleric", race="Nain")
    await call(client, "save_monster", name="Goblin", armor_class=15, hit_points=7)
    planned = await call(
        client,
        "plan_encounter",
        name="Ambush",
        monsters=[{"monster": "goblin", "count": 2, "at": ["f2", "F4"], "hidden": True}],
        battlefield={"width": 8, "height": 5, "walls": ["D1:D2"]},
    )
    assert "2 Goblin (hidden; at f2, F4)" in planned and "8x5 battle map" in planned
    bad = await call_error(
        client, "plan_encounter", name="Ambush", monsters=[{"monster": "goblin", "at": ["D1"]}]
    )
    assert "cannot stand on D1" in bad
    await call(
        client,
        "start_combat",
        participants=[{"name": "Borin", "initiative": 12}],
        encounter="Ambush",
    )
    state = await call(client, "get_game_state")
    assert "Goblin 1 F2" in state or "Goblin 2 F2" in state
    seen = json.loads(await call(client, "get_screen_data", view="combat"))
    assert all(t["hidden"] for t in seen["map"]["tokens"] if not t["party"])
    revealed = await call(client, "place_tokens", tokens=[{"who": "Goblin 1", "hidden": False}])
    assert "Goblin 1 (foe) F" in revealed
    caught = await call(client, "area_of_effect", shape="sphere", feet=5, at="F3")
    assert "foes: Goblin 1, Goblin 2 (hidden)" in caught
    target = await call(client, "check_target", attacker="Borin", target="Goblin 1")
    assert target.startswith("Borin to Goblin 1:")
