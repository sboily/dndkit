"""What only the game master sees: plans, statistics, secrets and notes."""

from gamemaster_mcp.errors import GameError
from gamemaster_mcp.game import bestiary
from gamemaster_mcp.models import NPC, Campaign, Encounter, Monster, Quest
from gamemaster_mcp.views.widgets import Json


def backstage(campaign: Campaign) -> Json:
    """Encounters still to fight, NPCs with their secrets, every quest, the bestiary."""
    return {
        "encounters": [
            _encounter(campaign, e) for e in campaign.encounters.values() if e.status != "done"
        ],
        "npcs": [_npc(n) for n in sorted(campaign.npcs.values(), key=lambda n: n.name)],
        "quests": [_quest(q) for q in campaign.quests.values()],
        "monsters": [
            _monster(m) for m in sorted(campaign.monsters.values(), key=lambda m: m.name)
        ],
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


def _npc(npc: NPC) -> Json:
    return {
        "name": npc.name,
        "attitude": npc.attitude,
        "occupation": npc.occupation,
        "location": npc.location,
        "description": npc.description,
        "bio": npc.bio,
        "notes": npc.notes,
    }


def _quest(quest: Quest) -> Json:
    return {
        "title": quest.title,
        "status": quest.status,
        "done": len(quest.completed_objectives),
        "total": len(quest.objectives),
        "reward": quest.reward,
        "notes": quest.notes,
    }


def _monster(monster: Monster) -> Json:
    return {
        "name": monster.name,
        "ac": monster.armor_class,
        "hp": monster.hit_points,
        "cr": monster.challenge_rating,
    }
