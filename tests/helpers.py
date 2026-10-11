"""Builders and MCP call helpers shared by the tests."""

from pathlib import Path

from fastmcp import Client

from gamemaster_mcp.models import Campaign, Character, CharacterClass, GameState, Race

FIXTURES = Path(__file__).parent / "fixtures"


def make_campaign() -> Campaign:
    return Campaign(name="Test", description="d", game_state=GameState(campaign_name="Test"))


def make_character(name: str = "Aria", hp: int = 10, **fields: object) -> Character:
    return Character.model_validate(
        {
            "name": name,
            "character_class": CharacterClass(name="Wizard"),
            "race": Race(name="Elf"),
            "hit_points_max": hp,
            "hit_points_current": hp,
            **fields,
        }
    )


async def call(client: Client, tool: str, **arguments: object) -> str:
    """Call a tool that must succeed; its text."""
    result = await client.call_tool(tool, arguments)
    return "\n".join(block.text for block in result.content if hasattr(block, "text"))


async def call_error(client: Client, tool: str, **arguments: object) -> str:
    """Call a tool that must fail; the message the model reads."""
    result = await client.call_tool(tool, arguments, raise_on_error=False)
    assert result.is_error, f"{tool} succeeded: {result.content}"
    return "\n".join(block.text for block in result.content if hasattr(block, "text"))
