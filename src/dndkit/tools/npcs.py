"""NPC tools."""

from collections.abc import Callable
from typing import Annotated

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from pydantic import Field

from dndkit.errors import InvalidChangeError
from dndkit.game import world
from dndkit.models import NPC, Attitude
from dndkit.storage import CampaignStore
from dndkit.tools import render
from dndkit.tools.deps import READ_ONLY, NameOrId, get_store, provided

Text = Annotated[str | None, Field(description="New value")]
Description = Annotated[str | None, Field(description="Public description")]
Bio = Annotated[str | None, Field(description="Private bio, secrets included")]
NpcAttitude = Annotated[Attitude | None, Field(description="Attitude towards the party")]


@tool
def create_npc(
    name: Annotated[str, Field(min_length=1, description="NPC name")],
    description: Description = None,
    bio: Bio = None,
    race: Annotated[str | None, Field(description="Race or species")] = None,
    occupation: Annotated[str | None, Field(description="Occupation")] = None,
    location: Annotated[str | None, Field(description="Where the NPC is")] = None,
    attitude: NpcAttitude = None,
    notes: Annotated[str, Field(description="Notes")] = "",
    store: CampaignStore = Depends(get_store),
) -> str:
    """Create an NPC. The name must be new; use update_npc to change one."""
    npc = NPC(
        name=name.strip(),
        description=description,
        bio=bio,
        race=race,
        occupation=occupation,
        location=location,
        attitude=attitude,
        notes=notes,
    )
    with store.transaction() as campaign:
        world.create_npc(campaign, npc)
    return f"Created NPC {npc.name} (id {npc.id})."


@tool(annotations=READ_ONLY)
def get_npc(name_or_id: NameOrId, store: CampaignStore = Depends(get_store)) -> str:
    """An NPC's details, private bio included (for the game master only)."""
    with store.reading() as campaign:
        return render.npc(world.find_npc(campaign, name_or_id))


@tool
def update_npc(
    name_or_id: NameOrId,
    name: Annotated[str | None, Field(description="New name")] = None,
    description: Description = None,
    bio: Bio = None,
    race: Text = None,
    occupation: Text = None,
    location: Text = None,
    attitude: NpcAttitude = None,
    notes: Text = None,
    store: CampaignStore = Depends(get_store),
) -> str:
    """Change an NPC: attitude, location, notes, secrets..."""
    changes = provided(
        name=name,
        description=description,
        bio=bio,
        race=race,
        occupation=occupation,
        location=location,
        attitude=attitude,
        notes=notes,
    )
    if not changes:
        raise InvalidChangeError("Nothing to change: give at least one field.")
    with store.transaction() as campaign:
        npc = world.update_npc(campaign, name_or_id, changes)
    return f"Updated NPC {npc.name}: {', '.join(changes)}."


@tool(annotations=READ_ONLY)
def list_npcs(store: CampaignStore = Depends(get_store)) -> str:
    """List NPCs with where they are."""
    with store.reading() as campaign:
        npcs = sorted(campaign.npcs.values(), key=lambda n: n.name)
        if not npcs:
            return "No NPCs yet."
        return "NPCs:\n" + "\n".join(
            f"- {n.name}{f', at {n.location}' if n.location else ''}" for n in npcs
        )


TOOLS: list[Callable[..., str]] = [create_npc, get_npc, update_npc, list_npcs]
