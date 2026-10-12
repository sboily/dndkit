"""Quest tools."""

from collections.abc import Callable
from typing import Annotated

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from pydantic import Field

from dndkit.errors import InvalidChangeError
from dndkit.game import world
from dndkit.models import Quest, QuestStatus
from dndkit.storage import CampaignStore
from dndkit.tools import render
from dndkit.tools.deps import READ_ONLY, NameOrId, get_store


@tool
def create_quest(
    title: Annotated[str, Field(min_length=1, description="Quest title")],
    description: Annotated[str, Field(description="What the quest is about")],
    giver: Annotated[str | None, Field(description="Who gave it (NPC name)")] = None,
    objectives: Annotated[list[str] | None, Field(description="Objectives, in order")] = None,
    reward: Annotated[str | None, Field(description="Promised reward")] = None,
    notes: Annotated[str, Field(description="Notes")] = "",
    store: CampaignStore = Depends(get_store),
) -> str:
    """Create an active quest. The title must be new."""
    quest = Quest(
        title=title.strip(),
        description=description,
        giver=giver,
        objectives=objectives or [],
        reward=reward,
        notes=notes,
    )
    with store.transaction() as campaign:
        world.create_quest(campaign, quest)
    return f"Created quest '{quest.title}' with {len(quest.objectives)} objective(s)."


@tool(annotations=READ_ONLY)
def get_quest(title_or_id: NameOrId, store: CampaignStore = Depends(get_store)) -> str:
    """A quest with its numbered objectives, each marked done or open."""
    with store.reading() as campaign:
        return render.quest(world.find_quest(campaign, title_or_id))


@tool
def update_quest(
    title_or_id: NameOrId,
    status: Annotated[QuestStatus | None, Field(description="New status")] = None,
    complete_objective: Annotated[
        str | None, Field(description="Objective done: its number (1, 2...) or its text")
    ] = None,
    add_objective: Annotated[str | None, Field(description="New objective to add")] = None,
    notes: Annotated[str | None, Field(description="Replaces the notes")] = None,
    store: CampaignStore = Depends(get_store),
) -> str:
    """Change a quest's status, complete or add an objective, or rewrite its notes."""
    if not any((status, complete_objective, add_objective, notes is not None)):
        raise InvalidChangeError("Nothing to change: give at least one field.")
    with store.transaction() as campaign:
        quest, changes = world.update_quest(
            campaign,
            title_or_id,
            status=status,
            complete_objective=complete_objective,
            add_objective=add_objective,
            notes=notes,
        )
    return f"Quest '{quest.title}': {'; '.join(changes) or 'unchanged'}."


@tool(annotations=READ_ONLY)
def list_quests(
    status: Annotated[
        QuestStatus | None, Field(description="Only quests with this status")
    ] = None,
    store: CampaignStore = Depends(get_store),
) -> str:
    """List quests with their status and progress."""
    with store.reading() as campaign:
        quests = [q for q in campaign.quests.values() if status is None or q.status == status]
        if not quests:
            return f"No {status} quests." if status else "No quests yet."
        rows = [
            f"- {q.title} [{q.status}], "
            f"{len(q.completed_objectives)}/{len(q.objectives)} objectives done"
            for q in sorted(quests, key=lambda q: q.created_at)
        ]
        return "Quests:\n" + "\n".join(rows)


TOOLS: list[Callable[..., str]] = [create_quest, get_quest, update_quest, list_quests]
