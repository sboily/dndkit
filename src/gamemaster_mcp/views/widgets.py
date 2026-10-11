"""The game as the game master sees it: the MCP widgets and the web backstage.

Everything shows here, monsters' exact hit points included; what the players
may see is built separately, field by field, in ``views.public``.
"""

from typing import Any

from gamemaster_mcp.game import characters
from gamemaster_mcp.game.dice import DiceLog, RollResult
from gamemaster_mcp.game.tables import XP_FOR_LEVEL
from gamemaster_mcp.models import ABILITIES, Campaign, Character, Combatant

Json = dict[str, Any]


def dice(log: DiceLog, limit: int = 6) -> Json:
    """The latest rolls, newest last."""
    return {"rolls": [_roll(n, t, r) for n, t, r in log.recent()[-limit:]]}


def _roll(number: int, at: float, result: RollResult) -> Json:
    return {
        "n": number,
        "t": at,
        "notation": result.notation,
        "total": result.total,
        "mode": result.mode,
        "terms": [
            {"sign": t.sign, "sides": t.sides, "faces": list(t.faces), "kept": t.kept}
            for t in result.terms
        ],
    }


def combat(campaign: Campaign) -> Json:
    """The initiative order with live hit points, and who has fallen."""
    state = campaign.game_state
    current = state.current_combatant
    return {
        "in_combat": state.in_combat,
        "round": state.combat_round,
        "order": [_combatant(campaign, c, c is current) for c in state.initiative_order],
        "defeated": [c.name for c in state.defeated],
        "xp": sum(c.xp for c in state.defeated),
    }


def _combatant(campaign: Campaign, combatant: Combatant, current: bool) -> Json:
    character = campaign.characters.get(combatant.character_id or "")
    if character is not None:
        stats = vitals(character)
    else:
        stats = {
            "hp": combatant.hit_points,
            "hp_max": combatant.hit_points_max,
            "temp": 0,
            "ac": combatant.armor_class,
            "conditions": combatant.conditions,
        }
    return {
        "name": combatant.name,
        "initiative": combatant.initiative,
        "pc": character is not None,
        "current": current,
        **stats,
    }


def party(campaign: Campaign) -> Json:
    """Where the party stands, every character's vitals and the quests' progress."""
    state = campaign.game_state
    current = state.current_combatant
    return {
        "campaign": campaign.name,
        "session": state.current_session,
        "location": state.current_location,
        "date": state.current_date_in_game,
        "funds": state.party_funds,
        "in_combat": state.in_combat,
        "round": state.combat_round,
        "current": current.name if current else None,
        "characters": [
            {"name": c.name, "summary": _summary(c), **vitals(c)}
            for c in sorted(campaign.characters.values(), key=lambda c: c.name)
        ],
        "quests": [
            {"title": q.title, "done": len(q.completed_objectives), "total": len(q.objectives)}
            for q in campaign.quests.values()
            if q.status == "active"
        ],
    }


def character(campaign: Campaign, ref: str) -> Json:
    """One character's sheet."""
    c = characters.find(campaign, ref)
    level = c.character_class.level
    return {
        "name": c.name,
        "summary": _summary(c),
        "player": c.player_name,
        "abilities": [
            {"key": key[:3], "score": c.abilities[key].score, "mod": c.abilities[key].mod}
            for key in ABILITIES
            if key in c.abilities
        ],
        "proficiency": c.proficiency_bonus,
        "xp": c.experience_points,
        "next_level_xp": XP_FOR_LEVEL.get(level + 1),
        "inspiration": c.inspiration,
        "inventory": [{"name": i.name, "qty": i.quantity} for i in c.inventory],
        "spells": [
            {"name": s.name, "level": s.level, "prepared": s.prepared}
            for s in sorted(c.spells_known, key=lambda s: (s.level, s.name))
        ],
        "features": c.features_and_traits,
        **vitals(c),
    }


def _summary(c: Character) -> str:
    return f"{c.race.name} {c.character_class.name} {c.character_class.level}"


def vitals(c: Character) -> Json:
    """Hit points, defenses and resources: what the whole table may see of a character."""
    return {
        "hp": c.hit_points_current,
        "hp_max": c.hit_points_max,
        "temp": c.temporary_hit_points,
        "ac": c.armor_class,
        "conditions": c.conditions,
        "exhaustion": c.exhaustion,
        "death_saves": [c.death_saves_success, c.death_saves_failure],
        "slots": [
            [level, maximum - c.spell_slots_used.get(level, 0), maximum]
            for level, maximum in sorted(c.spell_slots.items())
        ],
    }
