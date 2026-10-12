"""The table: who plays tonight, and which character each plays."""

from collections.abc import Callable
from typing import Annotated

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from pydantic import Field

from dndkit.config import ENV_WEB_HOST, ENV_WEB_PORT
from dndkit.errors import InvalidChangeError
from dndkit.game import seating
from dndkit.models import Seat, now
from dndkit.storage import CampaignStore
from dndkit.tools import render
from dndkit.tools.apps import JOIN_APP, SEATING_APP, app_meta
from dndkit.tools.deps import READ_ONLY, JoinCodes, get_join_codes, get_store


@tool(meta=app_meta(SEATING_APP))
def seat_players(
    players: Annotated[
        list[Seat] | None, Field(description="People sitting down, with their character")
    ] = None,
    leaving: Annotated[list[str] | None, Field(description="Players who left")] = None,
    start_over: Annotated[
        bool, Field(description="New session: forget who was here before")
    ] = False,
    store: CampaignStore = Depends(get_store),
) -> str:
    """Who is at the table and which character each plays (shown on screen).
    Without arguments, just shows it."""
    if not (players or leaving or start_over):
        with store.reading() as campaign:
            return render.table(campaign, store.opened_at)
    with store.transaction() as campaign:
        if start_over:
            seating.clear(campaign)
        notes = [seating.seat(campaign, s.player, s.character) for s in players or []]
        for player in leaving or []:
            seating.leave(campaign, player)
        campaign.game_state.roll_call_at = now()
        return "\n".join([*(note for note in notes if note), render.table(campaign)])


@tool(annotations=READ_ONLY, meta=app_meta(JOIN_APP))
def show_join_codes(
    store: CampaignStore = Depends(get_store),
    codes: JoinCodes | None = Depends(get_join_codes),
) -> str:
    """Show each character's QR code on screen: a player scans theirs to follow it on
    their phone."""
    if codes is None:
        raise InvalidChangeError(
            f"The web pages are off: the server needs {ENV_WEB_PORT} "
            f"(and {ENV_WEB_HOST}=0.0.0.0 for phones). Tell the game's host."
        )
    with store.reading() as campaign:
        shown = codes.view(campaign)
    names = ", ".join(p["name"] for p in shown["players"])
    if not names:
        return "No characters yet: the codes come with them."
    if not shown["reachable"]:
        return (
            f"Codes shown for {names}, but phones cannot reach this server: it needs "
            f"{ENV_WEB_HOST}=0.0.0.0. Tell the game's host."
        )
    return f"QR codes on screen for {names}: each player scans their character's."


TOOLS: list[Callable[..., str]] = [seat_players, show_join_codes]
