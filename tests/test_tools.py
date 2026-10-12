"""The MCP surface, through a real client: what roomkit-ui and other clients see."""

import json
import re
from pathlib import Path
from typing import Any

import pytest
from fastmcp import Client

from tests.helpers import call, call_error

pytestmark = pytest.mark.anyio

# roomkit-ui drops tools named outside this pattern.
TOOL_NAME = re.compile(r"[A-Za-z0-9_-]{1,64}")
# roomkit hides tools behind find_tools above about this many schema tokens
# (its default threshold, which roomkit-ui may raise).
TOOL_SEARCH_TOKENS = 8000
# The whole catalogue, skills off: past this, the tools need trimming.
CATALOGUE_CEILING = 9000
SKILLS = Path(__file__).parents[1] / "src" / "gamemaster_mcp" / "skills"


def walk_schemas(node: Any) -> list[dict[str, Any]]:
    """Every dict nested in a JSON schema."""
    if isinstance(node, dict):
        return [node, *(s for value in node.values() for s in walk_schemas(value))]
    if isinstance(node, list):
        return [s for item in node for s in walk_schemas(item)]
    return []


def skill_gated_tools() -> set[str]:
    """Tools the repository's skills gate: roomkit leaves them out until activated."""
    names: set[str] = set()
    for skill in SKILLS.glob("*/SKILL.md"):
        front = skill.read_text(encoding="utf-8").split("---")[1]
        names |= set(re.findall(r"^\s*-\s*(\w+)\s*$", front, re.MULTILINE))
    return names


def schema_tokens(tools: list[Any]) -> int:
    """roomkit's estimate: a quarter of the characters, per name, description, schema."""
    return sum(
        len(t.name) // 4 + len(t.description or "") // 4 + len(json.dumps(t.input_schema)) // 4 + 3
        for t in tools
    )


async def test_tool_catalogue_suits_voice_clients(client: Client) -> None:
    tools = await client.list_tools()
    assert len(tools) == 60
    assert all(TOOL_NAME.fullmatch(t.name) for t in tools)
    gated = skill_gated_tools()
    assert gated <= {t.name for t in tools}, "a skill gates a tool that does not exist"
    # With the skills enabled, roomkit sends the tools they do not gate.
    assert schema_tokens([t for t in tools if t.name not in gated]) < TOOL_SEARCH_TOKENS
    assert schema_tokens(tools) < CATALOGUE_CEILING
    for tool in tools:
        root = tool.input_schema
        assert "$defs" not in root and "store" not in root["properties"], tool.name
        for schema in walk_schemas(list(root["properties"].values())):
            assert "$ref" not in schema, tool.name
            # roomkit strips additionalProperties; a nested object must still say
            # what it holds, or Gemini refuses the whole tool list.
            if schema.get("type") == "object":
                assert schema.get("properties"), tool.name


async def test_game_errors_reach_the_model_as_errors(client: Client) -> None:
    message = await call_error(client, "get_character", name_or_id="Aria")
    assert "No campaign is active" in message
    await call(client, "create_campaign", name="Ghost", description="d")
    message = await call_error(client, "get_character", name_or_id="Aria")
    assert message == "No character named 'Aria'. Known characters: none yet."


async def test_character_changes_by_name_and_by_id(client: Client) -> None:
    await call(client, "create_campaign", name="Ghost", description="d")
    created = await call(
        client, "create_character", name="Aria", character_class="Wizard", race="Elf"
    )
    character_id = re.search(r"id (\w{8})", created)
    assert character_id is not None
    await call(client, "update_character", name_or_id="aria", strength=18, class_level=2)
    await call(client, "update_character", name_or_id=character_id.group(1), armor_class=13)
    await call(client, "add_item_to_character", character_name_or_id="ARIA", item_name="Staff")
    await call(client, "change_hit_points", names=["Aria"], amount=-4)
    sheet = await call(client, "get_character", name_or_id=character_id.group(1))
    assert "level 2 Elf Wizard, HP 2/6, AC 13" in sheet  # a d6 wizard, CON 10
    assert "STR 18 (+4)" in sheet and "Inventory: Staff x1" in sheet


async def test_failed_call_changes_nothing(client: Client) -> None:
    await call(client, "create_campaign", name="Ghost", description="d")
    await call(client, "create_character", name="Aria", character_class="Wizard", race="Elf")
    await call_error(client, "change_hit_points", names=["Aria", "Arya"], amount=-9)
    await call_error(client, "update_character", name_or_id="Aria", hit_points_current=99)
    assert "HP 6/6" in await call(client, "get_character", name_or_id="Aria")


async def test_combat_round_trip(client: Client) -> None:
    await call(client, "create_campaign", name="Ghost", description="d")
    started = await call(
        client,
        "start_combat",
        participants=[
            {"name": "Goblin", "initiative": 18},
            {"name": "Goblin", "initiative": 12},
            {"name": "Aria", "initiative": 5},
        ],
    )
    assert "Goblin 1 acts first" in started
    turns = [await call(client, "next_turn") for _ in range(3)]
    assert [t.split("'s turn")[0].split(". ")[-1] for t in turns] == [
        "Goblin 2",
        "Aria",
        "Goblin 1",
    ]
    assert "Current turn: Goblin 2" in await call(client, "remove_combatant", name="goblin 1")
    assert "In combat" in await call(client, "get_game_state")
    assert "round(s)" in await call(client, "end_combat")


async def test_events_belong_to_their_campaign(client: Client) -> None:
    await call(client, "create_campaign", name="First", description="d")
    await call(client, "add_event", event_type="combat", title="Ambush", description="Goblins")
    await call(client, "create_campaign", name="Second", description="d")
    assert await call(client, "get_events") == "No matching events."
    await call(client, "load_campaign", name="first")
    assert "Ambush" in await call(client, "get_events", search="goblin")


async def test_quests_show_progress_and_active_ones(client: Client) -> None:
    await call(client, "create_campaign", name="Ghost", description="d")
    await call(client, "create_quest", title="Lighthouse", description="d", objectives=["A", "B"])
    await call(client, "update_quest", title_or_id="lighthouse", complete_objective="1")
    assert "1/2 objectives done" in await call(client, "list_quests")
    assert "Active quests: Lighthouse" in await call(client, "get_game_state")


async def test_utilities_need_no_campaign(client: Client) -> None:
    assert "= " in await call(client, "roll_dice", notation="2d6+1d4+3")
    assert (await call(client, "roll_dice", notation="d20", secret=True)).startswith("Secret: d20")
    assert "Invalid dice notation" in await call_error(client, "roll_dice", notation="1d20abc")
    assert (await call(client, "lookup_rule", topic="à terre")).startswith("prone:")
    assert "Topics:" in await call_error(client, "lookup_rule", topic="dragon breath")


async def test_remove_from_campaign(client: Client) -> None:
    await call(client, "create_campaign", name="Ghost", description="d")
    await call(client, "create_npc", name="Bob")
    asked = await call(client, "remove_from_campaign", kind="npc", name_or_id="bob")
    assert asked.startswith("Nothing removed yet. Ask the user to confirm removing the npc 'Bob'")
    wrong = await call_error(
        client, "remove_from_campaign", kind="npc", name_or_id="bob", confirmation_code="zéro"
    )
    assert "wrong or expired, so nothing was removed" in wrong
    asked = await call(client, "remove_from_campaign", kind="npc", name_or_id="bob")
    code = asked.split("confirmation_code '")[1][:4]
    assert await call(
        client, "remove_from_campaign", kind="npc", name_or_id="bob", confirmation_code=code
    ) == ("Removed npc 'Bob'.")
    assert await call(client, "list_npcs") == "No NPCs yet."
