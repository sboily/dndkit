"""The web site: change notices, pages and guards, the stream, the server inside MCP."""

import json
import logging
import re
import shutil
import socket
import subprocess
import threading
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import anyio
import httpx
import pytest
from fastmcp import Client
from starlette.testclient import TestClient

from dndkit import ui
from dndkit.app import build_server
from dndkit.config import WebSettings
from dndkit.game import dice
from dndkit.game.dice import DiceLog
from dndkit.storage import CampaignStore
from dndkit.views import everyone
from dndkit.web import feed
from dndkit.web.changes import ACTIVITY, Changes
from dndkit.web.routes import create_app
from tests.helpers import call
from tests.web_helpers import aria_token, make_sources

WEB_PAGES = ["table", "player", "gm"]


@pytest.mark.anyio
async def test_a_change_in_a_worker_thread_wakes_the_feed() -> None:
    changes = Changes()
    threading.Timer(0.05, changes.notify).start()
    with anyio.fail_after(2):
        assert await changes.wait(0, timeout=5) == 1
    assert await changes.wait(1, timeout=0.01) == 1  # nothing new: times out
    threading.Timer(0.05, changes.close).start()
    with anyio.fail_after(2):
        await changes.wait(1, timeout=5)
    assert changes.closed


def test_saved_changes_and_rolls_are_reported_failed_changes_are_not(tmp_path: Path) -> None:
    seen: list[str] = []
    store = CampaignStore(tmp_path, on_change=lambda: seen.append("store"))
    store.create("Test", "d")
    with store.transaction() as campaign:
        campaign.world_notes = "kept"
    with pytest.raises(RuntimeError), store.transaction() as campaign:
        campaign.world_notes = "lost"
        raise RuntimeError
    DiceLog(on_record=lambda: seen.append("dice")).record(dice.roll("d20"))
    assert seen == ["store", "store", "dice"]


@pytest.mark.anyio
async def test_the_stream_sends_every_view_then_what_changed(tmp_path: Path) -> None:
    sources = make_sources(tmp_path)
    views = {
        "dice": feed.View(lambda: everyone.dice(sources.dice), "dice"),
        "party": feed.View(sources.reading(everyone.party), "party"),
    }
    events = feed.stream(sources.changes, views, sources.renders)
    with anyio.fail_after(5):
        assert await anext(events) == "retry: 2000\n\n"
        first = [await anext(events), await anext(events)]
        assert [event.split("\n")[0] for event in first] == ["event: dice", "event: party"]
        sources.dice.record(dice.roll("1d6"))
        changed = await anext(events)  # the party did not change: not sent again
        assert changed.startswith("event: dice\n")
        assert json.loads(changed.split("data: ", 1)[1])["rolls"][0]["notation"] == "1d6"
        sources.changes.close()
        with pytest.raises(StopAsyncIteration):
            await anext(events)


def test_a_view_renders_once_per_change_for_every_feed() -> None:
    changes, renders = Changes(), feed.Renders()
    counts = {"party": 0, "activity": 0}

    def counted(name: str) -> feed.Render:
        def render() -> dict[str, int]:
            counts[name] += 1
            return {"n": counts[name]}

        return render

    views = {
        "party": feed.View(counted("party"), "public/party"),
        "activity": feed.View(counted("activity"), "gm/activity", ACTIVITY),
    }
    for _ in range(10):  # ten pages open
        renders._all(views, changes.versions())
    assert counts == {"party": 1, "activity": 1}
    changes.notify_activity()  # a read-only tool call
    renders._all(views, changes.versions())
    assert counts == {"party": 1, "activity": 2}
    changes.notify()  # a change to the game
    renders._all(views, changes.versions())
    assert counts == {"party": 2, "activity": 2}


def site(tmp_path: Path, peer: str = "testclient") -> tuple[Any, TestClient]:
    sources = make_sources(tmp_path)
    return sources, TestClient(create_app(sources), client=(peer, 50000))


def test_pages_and_their_guards(tmp_path: Path) -> None:
    sources, client = site(tmp_path)
    assert client.get("/", follow_redirects=False).headers["location"] == "/table/"
    table = client.get("/table")
    assert table.status_code == 200 and 'window.GM_WEB = { feed: "feed" }' in table.text
    assert "default-src 'none'" in table.headers["content-security-policy"]
    assert client.get(f"/p/{aria_token(sources)}/").status_code == 200
    assert client.get(f"/p/{'a' * 16}/").status_code == 404
    assert client.get(f"/p/{'a' * 16}/feed?views=me").status_code == 404
    refused = client.get("/gm/", headers={"accept-language": "fr-CA,fr"})
    assert refused.status_code == 403 and "régie" in refused.text
    assert client.get("/gm/feed?views=backstage").status_code == 403
    assert client.get("/table/feed?views=backstage").status_code == 400  # not the table's
    assert client.get("/table/feed").status_code == 400


def test_the_backstage_opens_on_this_machine(tmp_path: Path) -> None:
    _, client = site(tmp_path, peer="127.0.0.1")
    assert client.get("/gm/").status_code == 200
    assert client.get("/gm/", headers={"host": "localhost:8765"}).status_code == 200


def test_the_backstage_refuses_a_rebound_name_or_a_proxy(tmp_path: Path) -> None:
    _, client = site(tmp_path, peer="127.0.0.1")
    rebound = {"host": "evil.example:8765"}  # a hostile page's domain, resolved to us
    assert client.get("/gm/feed?views=world", headers=rebound).status_code == 403
    for header in ("x-forwarded-for", "forwarded", "via"):
        assert client.get("/gm/", headers={header: "1.2.3.4"}).status_code == 403


def test_a_failing_view_leaves_the_others_running(tmp_path: Path) -> None:
    def broken() -> object:
        raise KeyError("oops")

    texts = feed.render_once(
        {"broken": feed.View(broken, "broken"), "fine": feed.View(lambda: {"ok": 1}, "fine")}
    )
    assert json.loads(texts["broken"]) == {"error": "viewFailed"}
    assert json.loads(texts["fine"]) == {"ok": 1}


@pytest.mark.parametrize("name", WEB_PAGES)
def test_web_pages_are_self_contained(name: str) -> None:
    html = ui.page(name, web=True)
    assert "<!--gm:shared-->" not in html and "const Views" in html
    assert not re.search(r"""(src|href)=["']https?://""", html), "pages must work offline"


def test_the_scripts_are_modules_inlined_in_order() -> None:
    folder = Path(ui.__file__).parent
    for index, name in enumerate(ui.SCRIPTS):
        imported = ui.IMPORT.findall((folder / name).read_text(encoding="utf-8"))
        assert all(ui.SCRIPTS.index(other) < index for other in imported), name
    html = ui.page("gm", web=True)
    assert not re.search(r"^(import|export) ", html, re.MULTILINE)
    assert "function CharacterSheet()" in html and "const Views = " in html


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
@pytest.mark.parametrize("name", ["dice", "combat", "party", "character", "seating", *WEB_PAGES])
def test_a_page_s_script_parses(name: str, tmp_path: Path) -> None:
    html = ui.page(name, web=name in WEB_PAGES)
    for number, script in enumerate(re.findall(r"<script>(.*?)</script>", html, re.DOTALL)):
        source = tmp_path / f"{number}.js"
        source.write_text(script, encoding="utf-8")
        subprocess.run(["node", "--check", str(source)], check=True, capture_output=True)


def test_widgets_keep_calling_mcp_tools() -> None:
    assert "window.GM_WEB = {" not in ui.page("dice")


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
        return port


async def next_event(lines: AsyncIterator[str]) -> Any:
    """The data of the next event of a stream."""
    async for line in lines:
        if line.startswith("data: "):
            return json.loads(line.removeprefix("data: "))
    raise AssertionError("the stream ended")


@pytest.mark.anyio
async def test_the_pages_follow_the_tools_live(tmp_path: Path) -> None:
    port = free_port()
    server = build_server(tmp_path, web=WebSettings(port=port))
    base = f"http://127.0.0.1:{port}"
    async with Client(server) as mcp, httpx.AsyncClient(base_url=base) as http:
        await call(mcp, "create_campaign", name="Live", description="d")
        assert (await http.get("/table/")).status_code == 200
        with anyio.fail_after(10):
            async with http.stream("GET", "/table/feed", params={"views": "dice"}) as response:
                lines = response.aiter_lines()
                assert await next_event(lines) == {"rolls": []}
                await call(mcp, "roll_dice", notation="2d6+1")
                rolls = (await next_event(lines))["rolls"]
                assert rolls[-1]["notation"].replace(" ", "") == "2d6+1"
            async with http.stream("GET", "/gm/feed", params={"views": "activity"}) as response:
                calls = (await next_event(response.aiter_lines()))["calls"]
                assert [c["name"] for c in calls] == ["roll_dice", "create_campaign"]


@pytest.mark.anyio
async def test_a_taken_port_leaves_the_game_running(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        settings = WebSettings(port=taken.getsockname()[1])
        with caplog.at_level(logging.WARNING, logger="dndkit.web.server"):
            async with Client(build_server(tmp_path, web=settings)) as mcp:
                await call(mcp, "create_campaign", name="Still here", description="d")
    assert "Web pages are off" in caplog.text
