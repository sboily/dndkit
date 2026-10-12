"""The game master's desk: the model's calls recorded, the notebook, full sheets."""

import json
from pathlib import Path
from typing import Any

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError

from gamemaster_mcp.activity import ActivityLog
from gamemaster_mcp.game import combat
from gamemaster_mcp.models import AdventureEvent, Item
from gamemaster_mcp.tools.recorder import Recorder
from gamemaster_mcp.views import desk
from gamemaster_mcp.web import audiences
from gamemaster_mcp.web.feed import _render_all
from tests.web_helpers import aria_token, make_sources

pytestmark = pytest.mark.anyio


def tiny_server(log: ActivityLog) -> FastMCP:
    server = FastMCP("tiny", middleware=[Recorder(log)])

    @server.tool
    def hit(name: str) -> str:
        """Hit someone."""
        if name == "nobody":
            raise ToolError("No one is called nobody.")
        return f"{name} is hit.\nHP 3/7"

    @server.tool
    def get_screen_data(view: str) -> str:
        """The widgets' own polling."""
        return view

    return server


async def test_every_call_is_recorded_with_its_answer_or_error() -> None:
    log = ActivityLog()
    async with Client(tiny_server(log)) as client:
        await client.call_tool("hit", {"name": "Goblin"})
        await client.call_tool("hit", {"name": "nobody"}, raise_on_error=False)
        await client.call_tool("get_screen_data", {"view": "dice"})
    calls = log.recent()
    assert [(c.name, c.failed) for c in calls] == [("hit", False), ("hit", True)]
    assert json.loads(calls[0].arguments) == {"name": "Goblin"}
    assert calls[0].outcome == "Goblin is hit.\nHP 3/7"
    assert calls[1].outcome == "No one is called nobody."
    view = desk.activity(log)
    assert [c["n"] for c in view["calls"]] == [2, 1] and view["failures"] == 1


def rendered(views: audiences.Views) -> dict[str, Any]:
    return {name: json.loads(text) for name, text in _render_all(views).items()}


def test_the_desk_is_the_game_masters_alone(tmp_path: Path) -> None:
    sources = make_sources(tmp_path)
    with sources.store.transaction() as campaign:
        campaign.game_state.notes = "The goblins wait at the bridge."
    sources.activity.record("tool", "next_turn", "{}", "Goblin's turn", False, 0.0)
    gm = rendered(audiences.game_master(sources, "http://127.0.0.1:8765/"))
    assert gm["notebook"]["situation"] == "The goblins wait at the bridge."
    assert gm["notebook"]["server"]["file"] == "Secrets.json"
    assert gm["sheets"]["sheets"][0]["notes"] == "SECRET-CHARACTER-NOTE"
    assert gm["activity"]["calls"][0]["name"] == "next_turn"
    assert gm["join"]["players"][0]["name"] == "Aria"
    for views in (
        audiences.table(sources, "http://127.0.0.1:8765/"),
        audiences.player(sources, aria_token(sources)),
    ):
        assert not {"notebook", "sheets", "activity"} & set(views)


def test_the_backstage_keeps_the_last_fight_and_the_whole_log(tmp_path: Path) -> None:
    sources = make_sources(tmp_path)
    with sources.store.transaction() as campaign:
        goblin = campaign.game_state.initiative_order[1]
        combat.remove(campaign.game_state, goblin.name)
        combat.end(campaign.game_state)
        campaign.encounters[next(iter(campaign.encounters))].status = "done"
        campaign.events = [
            AdventureEvent(event_type="combat", title="Ambush", description="d", importance=5)
        ]
        aria = next(iter(campaign.characters.values()))
        aria.equipment = {"main hand": Item(name="Staff", item_type="weapon", weight=4)}
    gm = rendered(audiences.game_master(sources, "http://127.0.0.1:8765/"))
    assert gm["combat"]["last"]["defeated"] == ["SECRET-SCOUT", "Goblin"]  # all, for the GM
    assert gm["combat"]["last"]["fighters"] == ["Aria", "SECRET-SCOUT", "Goblin"]
    assert gm["backstage"]["encounters"][0]["status"] == "done"
    assert gm["journal"]["events"][0]["importance"] == 5
    equipped = gm["sheets"]["sheets"][0]["equipment"][0]
    assert (equipped["slot"], equipped["details"]) == ("main hand", "weapon · 4 lb")
    table = rendered(audiences.table(sources, "http://127.0.0.1:8765/"))
    assert "importance" not in table["journal"]["events"][0]
