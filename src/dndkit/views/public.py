"""What the players may see: the table screen and each player's phone.

Built field by field from what is allowed, never by trimming the game
master's views, so a field added to a model stays hidden until it is added
here. Players see their party in full, but never an NPC's biography or notes,
a planned encounter, a monster's statistics, or a foe hidden from them: a
monster's hit points show as how hurt it looks.
"""

from dndkit.models import Campaign, Combatant
from dndkit.views.battle import battle_map, health, unseen
from dndkit.views.everyone import Json, vitals

JOURNAL_EVENTS = 8


def combat(campaign: Campaign) -> Json:
    """The initiative order; monsters without their numbers."""
    state = campaign.game_state
    current = state.current_combatant
    return {
        "in_combat": state.in_combat,
        "round": state.combat_round,
        "order": [
            _fighter(campaign, c, c is current) for c in state.initiative_order if not unseen(c)
        ],
        "defeated": [c.name for c in state.defeated if not unseen(c)],
        "xp": sum(c.xp for c in state.defeated if not unseen(c)),
        "map": battle_map(campaign, public=True),
    }


def _fighter(campaign: Campaign, combatant: Combatant, current: bool) -> Json:
    seen = {
        "name": combatant.name,
        "initiative": combatant.initiative,
        "current": current,
        "position": combatant.position,
        "boss": combatant.boss,
    }
    character = campaign.characters.get(combatant.character_id or "")
    if character is not None:
        return {**seen, "pc": True, **vitals(character)}
    return {
        **seen,
        "pc": False,
        "health": health(combatant.hit_points, combatant.hit_points_max),
        "conditions": list(combatant.conditions),
        "rounds": dict(combatant.condition_rounds),
    }


def journal(campaign: Campaign, limit: int = JOURNAL_EVENTS, full: bool = False) -> Json:
    """Active quests with their objectives, and the latest moments of the adventure log."""
    return {
        "quests": [
            {
                "title": q.title,
                "giver": q.giver,
                "description": q.description,
                "objectives": [
                    {"text": text, "done": text in q.completed_objectives} for text in q.objectives
                ],
            }
            for q in campaign.quests.values()
            if q.status == "active"
        ],
        "events": [
            {
                "title": e.title,
                "description": e.description,
                "type": e.event_type.value,
                "location": e.location,
                # The game master's own log adds what the players do not need.
                **(
                    {
                        "session": e.session_number,
                        "importance": e.importance,
                        "characters": e.characters_involved,
                        "tags": e.tags,
                    }
                    if full
                    else {}
                ),
            }
            for e in reversed(campaign.events[-limit:])
        ],
        "total": len(campaign.events),
    }
