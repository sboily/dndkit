"""Bestiary and encounter tools."""

from collections.abc import Callable
from typing import Annotated

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from pydantic import Field

from gamemaster_mcp.game import battlefield as battlefields
from gamemaster_mcp.game import bestiary
from gamemaster_mcp.models import EncounterGroup, Layout, Size
from gamemaster_mcp.storage import CampaignStore
from gamemaster_mcp.tools import render_combat
from gamemaster_mcp.tools.deps import READ_ONLY, get_store, provided

Text = Annotated[str | None, Field(description="Free text")]


@tool
def save_monster(
    name: Annotated[str, Field(min_length=1, description="Monster name, e.g. Goblin")],
    armor_class: Annotated[int | None, Field(ge=0, description="AC")] = None,
    hit_points: Annotated[int | None, Field(ge=1, description="Average HP")] = None,
    challenge_rating: Annotated[str | None, Field(description="CR, e.g. 1/4 or 3")] = None,
    xp: Annotated[int | None, Field(ge=0, description="XP; derived from CR if omitted")] = None,
    initiative_bonus: Annotated[int | None, Field(description="Dexterity modifier")] = None,
    speed: Annotated[str | None, Field(description="e.g. 30 ft., fly 60 ft.")] = None,
    size: Annotated[Size | None, Field(description="Size")] = None,
    actions: Annotated[str | None, Field(description="Attacks and abilities")] = None,
    notes: Text = None,
    store: CampaignStore = Depends(get_store),
) -> str:
    """Save or update a monster stat block; combatants named after it get its stats."""
    fields = provided(
        armor_class=armor_class,
        hit_points=hit_points,
        challenge_rating=challenge_rating,
        xp=xp,
        initiative_bonus=initiative_bonus,
        speed=speed,
        size=size,
        actions=actions,
        notes=notes,
    )
    with store.transaction() as campaign:
        monster, created = bestiary.save_monster(campaign, name, fields)
    return f"{'Saved' if created else 'Updated'} {render_combat.monster(monster)}"


@tool(annotations=READ_ONLY)
def get_monsters(
    name: Annotated[str | None, Field(description="One monster; omit to list all")] = None,
    store: CampaignStore = Depends(get_store),
) -> str:
    """A monster's stat block, or the whole bestiary."""
    with store.reading() as campaign:
        if name:
            return render_combat.monster(bestiary.find_monster(campaign, name))
        monsters = sorted(campaign.monsters.values(), key=lambda m: m.name)
        if not monsters:
            return "The bestiary is empty; add monsters with save_monster."
        return "\n".join(render_combat.monster(m).splitlines()[0] for m in monsters)


@tool
def plan_encounter(
    name: Annotated[str, Field(min_length=1, description="Encounter name")],
    monsters: Annotated[
        list[EncounterGroup] | None, Field(description="Bestiary monsters and how many")
    ] = None,
    description: Text = None,
    location: Annotated[str | None, Field(description="Where it happens")] = None,
    notes: Text = None,
    battlefield: Annotated[
        Layout | None, Field(description="Its battle map; monsters may then have squares")
    ] = None,
    store: CampaignStore = Depends(get_store),
) -> str:
    """Prepare (or change) a fight and rate its difficulty for the party.
    Run it later with start_combat(encounter=...), which lays out its map."""
    fields = provided(description=description, location=location, notes=notes)
    if battlefield is not None:
        fields["battlefield"] = battlefields.build(
            battlefield.width, battlefield.height, battlefield.walls, battlefield.difficult
        )
    with store.transaction() as campaign:
        encounter, created = bestiary.plan_encounter(campaign, name, monsters, fields)
        text = render_combat.encounter(campaign, encounter)
    return f"{'Planned' if created else 'Updated'} {text}"


@tool(annotations=READ_ONLY)
def list_encounters(store: CampaignStore = Depends(get_store)) -> str:
    """Planned encounters with their monsters, status and difficulty."""
    with store.reading() as campaign:
        encounters = list(campaign.encounters.values())
        if not encounters:
            return "No encounter planned."
        return "\n".join(f"- {render_combat.encounter(campaign, e)}" for e in encounters)


TOOLS: list[Callable[..., str]] = [save_monster, get_monsters, plan_encounter, list_encounters]
