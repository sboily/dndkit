"""The game master's plans: encounters still to fight and quests, notes included."""

from gamemaster_mcp.errors import GameError
from gamemaster_mcp.game import bestiary
from gamemaster_mcp.models import Campaign, Encounter, Quest
from gamemaster_mcp.views.widgets import Json


def backstage(campaign: Campaign) -> Json:
    """The plans: encounters still to fight, and every quest with its notes."""
    return {
        "encounters": [
            _encounter(campaign, e) for e in campaign.encounters.values() if e.status != "done"
        ],
        "quests": [_quest(q) for q in campaign.quests.values()],
    }


def _encounter(campaign: Campaign, encounter: Encounter) -> Json:
    try:
        rated = bestiary.difficulty(campaign, encounter)
    except GameError:  # a monster since removed from the bestiary
        rated = None
    return {
        "name": encounter.name,
        "status": encounter.status,
        "location": encounter.location,
        "description": encounter.description,
        "notes": encounter.notes,
        "monsters": [f"{g.count}× {g.monster}" for g in encounter.monsters],
        "difficulty": rated.rating if rated else None,
        "xp": rated.adjusted_xp if rated else None,
    }


def _quest(quest: Quest) -> Json:
    return {
        "title": quest.title,
        "status": quest.status,
        "giver": quest.giver,
        "description": quest.description,
        "objectives": [
            {"text": text, "done": text in quest.completed_objectives} for text in quest.objectives
        ],
        "done": len(quest.completed_objectives),
        "total": len(quest.objectives),
        "reward": quest.reward,
        "notes": quest.notes,
    }
