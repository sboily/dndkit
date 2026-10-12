"""NPCs, locations and quests, and removing any campaign entity."""

from collections.abc import Mapping
from typing import Any, Literal

from gamemaster_mcp.errors import NotFoundError
from gamemaster_mcp.game import combat, registry
from gamemaster_mcp.models import NPC, Campaign, Location, Quest, QuestStatus

EntityKind = Literal["character", "npc", "location", "quest"]
NPC_KIND = "NPC"
LOCATION_KIND = "location"
QUEST_KIND = "quest"

# kind -> (Campaign attribute, label used in messages)
_COLLECTIONS: dict[str, tuple[str, str]] = {
    "character": ("characters", "character"),
    "npc": ("npcs", NPC_KIND),
    "location": ("locations", LOCATION_KIND),
    "quest": ("quests", QUEST_KIND),
}


def find_entity(campaign: Campaign, kind: EntityKind, ref: str) -> registry.Named:
    """The character, NPC, location or quest *ref* names."""
    attribute, label = _COLLECTIONS[kind]
    found: registry.Named = registry.find(getattr(campaign, attribute), ref, label)
    return found


def remove_entity(campaign: Campaign, kind: EntityKind, ref: str) -> str:
    """Remove a character, NPC, location or quest; returns its name. A character
    leaves the running fight too."""
    attribute, label = _COLLECTIONS[kind]
    removed: registry.Named = registry.remove(getattr(campaign, attribute), ref, label)
    state = campaign.game_state
    for fighter in [c for c in state.initiative_order if c.character_id == removed.id]:
        combat.remove(state, fighter.name, overcome=False)
    return removed.name


def find_npc(campaign: Campaign, ref: str) -> NPC:
    """The NPC *ref* names."""
    return registry.find(campaign.npcs, ref, NPC_KIND)


def create_npc(campaign: Campaign, npc: NPC) -> NPC:
    """Add an NPC; the name must be free."""
    return registry.add(campaign.npcs, npc, NPC_KIND)


def update_npc(campaign: Campaign, ref: str, changes: Mapping[str, Any]) -> NPC:
    """Change an NPC's fields."""
    return registry.update(campaign.npcs, ref, NPC_KIND, changes)


def find_location(campaign: Campaign, ref: str) -> Location:
    """The location *ref* names."""
    return registry.find(campaign.locations, ref, LOCATION_KIND)


def create_location(campaign: Campaign, location: Location) -> Location:
    """Add a location; the name must be free."""
    return registry.add(campaign.locations, location, LOCATION_KIND)


def update_location(campaign: Campaign, ref: str, changes: Mapping[str, Any]) -> Location:
    """Change a location's fields."""
    return registry.update(campaign.locations, ref, LOCATION_KIND, changes)


def find_quest(campaign: Campaign, ref: str) -> Quest:
    """The quest *ref* names (title or ID)."""
    return registry.find(campaign.quests, ref, QUEST_KIND)


def create_quest(campaign: Campaign, quest: Quest) -> Quest:
    """Add a quest; the title must be free."""
    return registry.add(campaign.quests, quest, QUEST_KIND)


def update_quest(
    campaign: Campaign,
    ref: str,
    *,
    status: QuestStatus | None = None,
    complete_objective: str | None = None,
    add_objective: str | None = None,
    notes: str | None = None,
) -> tuple[Quest, list[str]]:
    """Change a quest; returns it with a line per change made."""
    quest = find_quest(campaign, ref)
    changes: list[str] = []
    if add_objective and add_objective not in quest.objectives:
        quest.objectives = [*quest.objectives, add_objective]
        changes.append(f"new objective '{add_objective}'")
    if complete_objective:
        objective = _match_objective(quest, complete_objective)
        if objective not in quest.completed_objectives:
            quest.completed_objectives = [*quest.completed_objectives, objective]
        changes.append(f"objective done: '{objective}'")
    if status:
        quest.status = status
        changes.append(f"status {status}")
    if notes is not None:
        quest.notes = notes
        changes.append("notes updated")
    return quest, changes


def _match_objective(quest: Quest, ref: str) -> str:
    """An objective by number ("2"), exact text, or a fragment only it contains."""
    text = ref.strip()
    if text.isdigit() and 1 <= int(text) <= len(quest.objectives):
        return quest.objectives[int(text) - 1]
    wanted = registry.normalize(text)
    exact = [o for o in quest.objectives if registry.normalize(o) == wanted]
    partial = [o for o in quest.objectives if wanted and wanted in registry.normalize(o)]
    matches = exact or partial
    if len(matches) == 1:
        return matches[0]
    listed = "; ".join(f"{i}. {o}" for i, o in enumerate(quest.objectives, 1)) or "none"
    raise NotFoundError(
        f"Quest '{quest.title}' has no single objective matching '{ref}'. Objectives: {listed}."
    )
