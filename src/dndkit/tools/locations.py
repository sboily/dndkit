"""Location tools."""

from collections.abc import Callable
from typing import Annotated

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from pydantic import Field

from dndkit.errors import InvalidChangeError
from dndkit.game import world
from dndkit.models import Location
from dndkit.storage import CampaignStore
from dndkit.tools import render
from dndkit.tools.deps import READ_ONLY, NameOrId, get_store, provided

Text = Annotated[str | None, Field(description="New value")]
Population = Annotated[int | None, Field(ge=0, description="Population")]
Features = Annotated[list[str] | None, Field(description="Notable features")]


@tool
def create_location(
    name: Annotated[str, Field(min_length=1, description="Location name")],
    location_type: Annotated[str, Field(description="city, town, village, dungeon, forest...")],
    description: Annotated[str, Field(description="What it looks and feels like")],
    population: Population = None,
    government: Annotated[str | None, Field(description="Who rules it")] = None,
    notable_features: Features = None,
    notes: Annotated[str, Field(description="Notes")] = "",
    store: CampaignStore = Depends(get_store),
) -> str:
    """Create a location. The name must be new; use update_location to change one."""
    location = Location(
        name=name.strip(),
        location_type=location_type,
        description=description,
        population=population,
        government=government,
        notable_features=notable_features or [],
        notes=notes,
    )
    with store.transaction() as campaign:
        world.create_location(campaign, location)
    return f"Created location {location.name} ({location.location_type}, id {location.id})."


@tool(annotations=READ_ONLY)
def get_location(name_or_id: NameOrId, store: CampaignStore = Depends(get_store)) -> str:
    """A location's description, features, NPCs and connections."""
    with store.reading() as campaign:
        return render.location(world.find_location(campaign, name_or_id))


@tool
def update_location(
    name_or_id: NameOrId,
    name: Annotated[str | None, Field(description="New name")] = None,
    location_type: Text = None,
    description: Text = None,
    population: Population = None,
    government: Text = None,
    notable_features: Features = None,
    npcs: Annotated[list[str] | None, Field(description="NPC names found here")] = None,
    connections: Annotated[list[str] | None, Field(description="Linked locations")] = None,
    notes: Text = None,
    store: CampaignStore = Depends(get_store),
) -> str:
    """Change a location. Lists given here replace the stored ones."""
    changes = provided(
        name=name,
        location_type=location_type,
        description=description,
        population=population,
        government=government,
        notable_features=notable_features,
        npcs=npcs,
        connections=connections,
        notes=notes,
    )
    if not changes:
        raise InvalidChangeError("Nothing to change: give at least one field.")
    with store.transaction() as campaign:
        location = world.update_location(campaign, name_or_id, changes)
    return f"Updated location {location.name}: {', '.join(changes)}."


@tool(annotations=READ_ONLY)
def list_locations(store: CampaignStore = Depends(get_store)) -> str:
    """List locations with their type."""
    with store.reading() as campaign:
        places = sorted(campaign.locations.values(), key=lambda loc: loc.name)
        if not places:
            return "No locations yet."
        return "Locations:\n" + "\n".join(f"- {p.name} ({p.location_type})" for p in places)


TOOLS: list[Callable[..., str]] = [create_location, get_location, update_location, list_locations]
