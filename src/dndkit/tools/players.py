"""The table: who plays tonight, and which character each plays."""

from collections.abc import Callable
from typing import Annotated

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from pydantic import Field

from dndkit.game import seating
from dndkit.models import Seat, now
from dndkit.storage import CampaignStore
from dndkit.tools import render
from dndkit.tools.apps import SEATING_APP, app_meta
from dndkit.tools.deps import get_store


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


TOOLS: list[Callable[..., str]] = [seat_players]
