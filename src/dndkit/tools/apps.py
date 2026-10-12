"""MCP Apps: which tools open a widget, and the page each widget loads.

A tool whose ``_meta.ui.resourceUri`` names a ``ui://`` resource opens that
page in clients that support MCP Apps (roomkit-ui shows it in the chat);
other clients ignore the metadata. roomkit-ui hands a page only the tool's
text result, so each page reads its data from ``get_screen_data`` instead.
"""

from collections.abc import Callable
from typing import Any

from fastmcp import FastMCP

from dndkit import ui

DICE_APP = "ui://dndkit/dice.html"
COMBAT_APP = "ui://dndkit/combat.html"
PARTY_APP = "ui://dndkit/party.html"
CHARACTER_APP = "ui://dndkit/character.html"
SEATING_APP = "ui://dndkit/seating.html"
JOIN_APP = "ui://dndkit/join.html"

_PAGES = {
    DICE_APP: ("dice", "Dice tray: the latest roll, rolling."),
    COMBAT_APP: ("combat", "Combat tracker: initiative, hit points, conditions, live."),
    PARTY_APP: ("party", "Party board: hit points, conditions, location and quests, live."),
    CHARACTER_APP: ("character", "Character sheet, live."),
    SEATING_APP: ("seating", "The table: who plays which character tonight, live."),
    JOIN_APP: ("join", "Join codes: each character's QR code, for the players' phones."),
}


def app_meta(uri: str) -> dict[str, Any]:
    """Tool metadata that opens the page at *uri*."""
    return {"ui": {"resourceUri": uri}}


def register_apps(server: FastMCP) -> None:
    """Serve every page as a ``ui://`` resource (MIME text/html;profile=mcp-app)."""
    for uri, (name, description) in _PAGES.items():
        server.resource(uri, name=f"{name}-app", description=description)(_loader(name))


def _loader(name: str) -> Callable[[], str]:
    def load() -> str:
        return ui.page(name)

    load.__name__ = f"{name}_app"
    return load
