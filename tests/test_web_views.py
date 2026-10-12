"""What each web audience sees, the players' links, and the web settings."""

import json
import stat
from pathlib import Path

import pytest

from gamemaster_mcp.config import WebSettings, resolve_web_settings
from gamemaster_mcp.views.battle import health
from gamemaster_mcp.web import access, audiences
from gamemaster_mcp.web.access import PlayerLinks
from gamemaster_mcp.web.feed import _render_all
from tests.web_helpers import aria_token, make_sources


def rendered(views: audiences.Views) -> dict[str, dict]:
    return {name: json.loads(text) for name, text in _render_all(views).items()}


def test_the_table_and_the_players_see_no_secret(tmp_path: Path) -> None:
    sources = make_sources(tmp_path)
    for views in (
        audiences.table(sources, "http://127.0.0.1:8765/"),
        audiences.player(sources, aria_token(sources)),
    ):
        data = rendered(views)
        assert "SECRET" not in json.dumps(data, ensure_ascii=False)
        goblin = data["combat"]["order"][1]
        assert goblin == {
            "name": "Goblin",
            "initiative": 12,
            "current": False,
            "position": None,
            "boss": False,
            "pc": False,
            "health": "bloodied",
            "conditions": [],
        }
        assert data["combat"]["order"][0]["hp"] == 12  # the party in full


def test_the_game_master_sees_everything(tmp_path: Path) -> None:
    sources = make_sources(tmp_path)
    data = rendered(audiences.game_master(sources, "http://127.0.0.1:8765/"))
    text = json.dumps(data)
    for secret in ("SECRET-BIO", "SECRET-NPC", "SECRET-AMBUSH", "SECRET-QUEST"):
        assert secret in text
    assert data["combat"]["order"][1]["hp"] == 3
    assert data["backstage"]["encounters"][0]["difficulty"] == "deadly"


def test_the_backstage_world_holds_npcs_places_and_stat_blocks(tmp_path: Path) -> None:
    sources = make_sources(tmp_path)
    with sources.store.transaction() as campaign:
        campaign.game_state.current_location = "port"
        campaign.game_state.initiative_order[1].monster = "Goblin"
    world = rendered(audiences.game_master(sources, "http://127.0.0.1:8765/"))["world"]
    assert [n["name"] for n in world["npcs"]] == ["Mara"] and world["npcs"][0][
        "bio"
    ] == "SECRET-BIO"
    assert world["locations"][0]["current"] is True
    assert world["locations"][0]["notes"] == "SECRET-PLACE"
    goblin = next(m for m in world["monsters"] if m["name"] == "Goblin")
    assert goblin["fighting"] == 1 and goblin["notes"] == "SECRET-GOBLIN"
    assert "world" not in audiences.table(sources, "http://127.0.0.1:8765/")
    assert "world" not in audiences.player(sources, aria_token(sources))


def test_a_player_gets_their_own_sheet(tmp_path: Path) -> None:
    sources = make_sources(tmp_path)
    data = rendered(audiences.player(sources, aria_token(sources)))
    assert data["me"]["name"] == "Aria"
    assert data["party"]["campaign"] == "Secrets"
    assert data["party"]["description"] == "A campaign with things to hide"
    assert data["journal"]["quests"][0]["objectives"] == [
        {"text": "Reach the tower", "done": True},
        {"text": "Ring the bell", "done": False},
    ]


def test_a_stale_link_says_so(tmp_path: Path) -> None:
    sources = make_sources(tmp_path)
    data = rendered(audiences.player(sources, "a" * 16))
    assert data["me"] == {"error": "unknownLink"}


@pytest.mark.parametrize(
    ("hp", "maximum", "looks"),
    [(7, 7, "unhurt"), (5, 7, "hurt"), (3, 7, "bloodied"), (0, 7, "down"), (None, 7, None)],
)
def test_how_hurt_a_monster_looks(hp: int | None, maximum: int, looks: str | None) -> None:
    assert health(hp, maximum) == looks


def test_links_are_stable_secret_and_per_campaign(tmp_path: Path) -> None:
    sources = make_sources(tmp_path)
    token = aria_token(sources)
    reopened = PlayerLinks.open(tmp_path)
    with sources.store.reading() as campaign:
        assert reopened.character_for(campaign, token) is not None
        assert reopened.character_for(campaign, token.upper()) is None
        assert reopened.character_for(campaign, "é" * 16) is None
    key = tmp_path / access.KEY_FILE
    assert stat.S_IMODE(key.stat().st_mode) == 0o600
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    with sources.store.reading() as campaign:  # another key, another token
        assert PlayerLinks.open(elsewhere).character_for(campaign, token) is None


def test_a_cut_short_key_is_replaced(tmp_path: Path) -> None:
    (tmp_path / access.KEY_FILE).write_bytes(b"short")
    PlayerLinks.open(tmp_path)
    assert len((tmp_path / access.KEY_FILE).read_bytes()) == access.SECRET_BYTES


def test_phones_get_a_reachable_address(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(access, "lan_address", lambda: "192.168.1.20")
    everywhere = WebSettings(port=8765, host="0.0.0.0")  # nosec B104
    local_only = WebSettings(port=8765)
    named = WebSettings(port=8765, public_url="https://table.example")
    assert access.phone_base_url(everywhere, "http://127.0.0.1:8765/") == (
        "http://192.168.1.20:8765",
        True,
    )
    assert access.phone_base_url(everywhere, "http://10.0.0.5:8765/") == (
        "http://10.0.0.5:8765",
        True,
    )
    assert access.phone_base_url(local_only, "http://localhost:8765/") == (
        "http://localhost:8765",
        False,
    )
    assert access.phone_base_url(named, "http://127.0.0.1:8765/") == (
        "https://table.example",
        True,
    )


def test_web_settings_come_from_the_environment() -> None:
    assert resolve_web_settings({}) is None
    assert resolve_web_settings({"GAMEMASTER_WEB_PORT": "eighty"}) is None
    assert resolve_web_settings({"GAMEMASTER_WEB_PORT": "99999"}) is None
    assert resolve_web_settings({"GAMEMASTER_WEB_PORT": "²"}) is None  # a digit, not a number
    no_scheme = {"GAMEMASTER_WEB_PORT": "8765", "GAMEMASTER_WEB_URL": "table.local:8765"}
    assert resolve_web_settings(no_scheme) == WebSettings(8765)
    settings = resolve_web_settings(
        {
            "GAMEMASTER_WEB_PORT": " 8765 ",
            "GAMEMASTER_WEB_HOST": "0.0.0.0",  # nosec B104
            "GAMEMASTER_WEB_URL": "http://table.local:8765/",
        }
    )
    assert settings == WebSettings(8765, "0.0.0.0", "http://table.local:8765")  # nosec B104
