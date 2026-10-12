"""Progression tools: experience and levelling up."""

from collections.abc import Callable
from typing import Annotated

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from pydantic import Field

from dndkit.game import progression
from dndkit.storage import CampaignStore
from dndkit.tools.deps import NameOrId, get_store


@tool
def award_experience(
    total_xp: Annotated[int, Field(ge=1, description="XP to split, e.g. the monsters' total")],
    names_or_ids: Annotated[
        list[str] | None, Field(description="Who shares it; omit for the whole party")
    ] = None,
    store: CampaignStore = Depends(get_store),
) -> str:
    """Split XP evenly and say who has enough for a new level."""
    with store.transaction() as campaign:
        return "\n".join(progression.award_experience(campaign, names_or_ids or [], total_xp))


@tool
def level_up(
    name_or_id: NameOrId,
    hit_die_roll: Annotated[
        int | None, Field(ge=1, le=12, description="The hit die roll; omit for the average")
    ] = None,
    store: CampaignStore = Depends(get_store),
) -> str:
    """Raise a character one level: HP (die + CON), proficiency, hit dice, spell slots."""
    with store.transaction() as campaign:
        return progression.level_up(campaign, name_or_id, hit_die_roll)


TOOLS: list[Callable[..., str]] = [award_experience, level_up]
