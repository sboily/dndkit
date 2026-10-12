"""MCP Apps, screen data, compact schemas, and a full fight through the tools."""

import json
import re

import pytest
from fastmcp import Client

from tests.helpers import call, call_error

pytestmark = pytest.mark.anyio

APP_TOOLS = {
    "roll_dice": "ui://dndkit/dice.html",
    "start_combat": "ui://dndkit/combat.html",
    "get_game_state": "ui://dndkit/party.html",
    "seat_players": "ui://dndkit/seating.html",
    "get_character": "ui://dndkit/character.html",
}


async def test_app_tools_point_at_served_pages(client: Client) -> None:
    tools = {t.name: t for t in await client.list_tools()}
    for name, uri in APP_TOOLS.items():
        assert (tools[name].meta or {}).get("ui", {}).get("resourceUri") == uri
    resources = {str(r.uri): r for r in await client.list_resources()}
    for uri in APP_TOOLS.values():
        assert resources[uri].mime_type == "text/html;profile=mcp-app"
        html = (await client.read_resource(uri))[0].text
        assert "<!--gm:shared-->" not in html and "const GM" in html
        assert not re.search(r"""(src|href)=["']https?://""", html), "pages must work offline"


async def test_optional_parameters_are_advertised_without_null(client: Client) -> None:
    for tool in await client.list_tools():
        text = json.dumps(tool.input_schema)
        assert '{"type": "null"}' not in text, tool.name
        assert '"default": null' not in text, tool.name


async def test_screen_data_for_each_widget(client: Client) -> None:
    await call(client, "roll_dice", notation="d20+2", advantage=True)
    dice = json.loads(await call(client, "get_screen_data", view="dice"))
    last = dice["rolls"][-1]
    assert last["mode"] == "advantage" and len(last["terms"][0]["faces"]) == 2
    assert "No campaign is active" in await call_error(client, "get_screen_data", view="party")
    await call(client, "create_campaign", name="Ghost", description="d")
    await call(client, "create_character", name="Aria", character_class="Wizard", race="Elf")
    party = json.loads(await call(client, "get_screen_data", view="party"))
    assert party["characters"][0]["name"] == "Aria" and party["in_combat"] is False
    await call(client, "seat_players", players=[{"player": "Ana", "character": "aria"}])
    seats = json.loads(await call(client, "get_screen_data", view="seating"))
    assert seats["seats"] == [
        {"player": "Ana", "characters": [{"name": "Aria", "summary": "Elf Wizard 1"}]}
    ]
    sheet = json.loads(await call(client, "get_screen_data", view="character", name="aria"))
    assert sheet["abilities"][0] == {"key": "str", "score": 10, "mod": 0}
    assert "needs a name" in await call_error(client, "get_screen_data", view="character")


async def test_a_planned_fight_from_start_to_level_up(client: Client) -> None:
    await call(client, "create_campaign", name="Ghost", description="d")
    await call(
        client,
        "create_character",
        name="Aria",
        character_class="Magicien",
        race="Elf",
        hit_points_max=8,
    )
    await call(
        client, "save_monster", name="Goblin", armor_class=15, hit_points=7, challenge_rating="1/4"
    )
    planned = await call(
        client, "plan_encounter", name="Ambush", monsters=[{"monster": "goblin", "count": 6}]
    )
    assert "Difficulty deadly" in planned
    started = await call(
        client,
        "start_combat",
        participants=[{"name": "Aria", "initiative": 30}],
        encounter="ambush",
    )
    assert "Aria acts first" in started and "Goblin 6" in started
    for number in range(1, 7):
        await call(client, "change_hit_points", names=[f"Goblin {number}"], amount=-7)
    combat_view = json.loads(await call(client, "get_screen_data", view="combat"))
    assert [f["name"] for f in combat_view["order"]] == ["Aria"] and combat_view["xp"] == 300
    ended = await call(client, "end_combat")
    assert "Goblin 1" in ended and "300 XP" in ended
    assert "enough for level 2" in await call(client, "award_experience", total_xp=300)
    assert "reaches level 2" in await call(client, "level_up", name_or_id="Aria")
    assert "[done]" in await call(client, "list_encounters")


async def test_conditions_and_rest_through_the_tools(client: Client) -> None:
    await call(client, "create_campaign", name="Ghost", description="d")
    await call(
        client, "create_character", name="Aria", character_class="Occultiste", race="Tiefling"
    )
    await call(client, "set_condition", names=["Aria"], condition="poisoned")
    assert "Conditions: poisoned" in await call(client, "get_character", name_or_id="Aria")
    await call(client, "set_spell_slots", character_name_or_id="Aria", level=1, max_slots=1)
    await call(client, "use_spell_slot", character_name_or_id="Aria", level=1)
    assert "pact slots restored" in await call(client, "rest", kind="short")
