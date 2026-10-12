"""The game as the game master sees it: the MCP widgets and the web backstage.

Everything shows here, monsters' exact hit points included; what the players
may see is built separately, field by field, in ``views.public``.
"""

from typing import Any

from gamemaster_mcp.game import characters, seating
from gamemaster_mcp.game.dice import DiceLog, RollResult
from gamemaster_mcp.game.tables import XP_FOR_LEVEL
from gamemaster_mcp.models import ABILITIES, Campaign, Character, Combatant, Spell
from gamemaster_mcp.views.battle import battle_map, unseen

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
        "map": battle_map(campaign, public=False),
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
        "position": combatant.position,
        "hidden": combatant.hidden,
        "boss": combatant.boss,
        "legendary": [combatant.legendary_actions_left, combatant.legendary_actions],
        "resistances": combatant.legendary_resistances_left,
        **stats,
    }


def party(campaign: Campaign) -> Json:
    """Where the party stands, every character's vitals and the quests' progress."""
    state = campaign.game_state
    current = state.current_combatant
    return {
        "campaign": campaign.name,
        "description": campaign.description,
        "session": state.current_session,
        "location": state.current_location,
        "date": state.current_date_in_game,
        "funds": state.party_funds,
        "in_combat": state.in_combat,
        "round": state.combat_round,
        # The players' pages show this too: a hidden foe's turn names no one.
        "current": current.name if current and not unseen(current) else None,
        "characters": [
            {
                "name": c.name,
                "summary": _summary(c),
                "player": c.player_name,
                "present": seating.is_present(campaign, c),
                **vitals(c),
            }
            for c in sorted(campaign.characters.values(), key=lambda c: c.name)
        ],
        "quests": [
            {"title": q.title, "done": len(q.completed_objectives), "total": len(q.objectives)}
            for q in campaign.quests.values()
            if q.status == "active"
        ],
    }


def seating_chart(campaign: Campaign) -> Json:
    """Who sits at the table in seat order, with their characters, and who is missing."""
    state = campaign.game_state
    party = sorted(campaign.characters.values(), key=lambda c: c.name)
    return {
        "campaign": campaign.name,
        "session": state.current_session,
        "called": bool(state.players_present),
        "seats": [
            {
                "player": player,
                "characters": [
                    {"name": c.name, "summary": _summary(c)}
                    for c in seating.characters_of(campaign, player)
                ],
            }
            for player in state.players_present
        ],
        # Before the roll call: the players known so far.
        "absent": [
            {"name": c.name, "player": c.player_name}
            for c in party
            if c.player_name and (not state.players_present or not seating.is_present(campaign, c))
        ],
        "unplayed": [c.name for c in party if not c.player_name],
    }


def character(campaign: Campaign, ref: str) -> Json:
    """One character's sheet, as its player sees it (the game master's notes left out)."""
    c = characters.find(campaign, ref)
    level = c.character_class.level
    casting = characters.spellcasting(c)
    return {
        "name": c.name,
        "summary": _summary(c),
        "player": c.player_name,
        "background": c.background,
        "alignment": c.alignment,
        "description": c.description,
        "bio": c.bio,
        "abilities": [
            {"key": key[:3], "score": c.abilities[key].score, "mod": c.abilities[key].mod}
            for key in ABILITIES
            if key in c.abilities
        ],
        "proficiency": c.proficiency_bonus,
        "speed": c.speed,
        "initiative": characters.initiative(c),
        "hit_dice": c.hit_dice_remaining,
        "casting": (
            {"ability": casting.ability, "attack": casting.attack, "dc": casting.save_dc}
            if casting
            else None
        ),
        "xp": c.experience_points,
        "next_level_xp": XP_FOR_LEVEL.get(level + 1),
        "inspiration": c.inspiration,
        "inventory": [
            {"name": i.name, "qty": i.quantity, "description": i.description} for i in c.inventory
        ],
        "spells": [_spell(s) for s in sorted(c.spells_known, key=lambda s: (s.level, s.name))],
        "features": c.features_and_traits,
        "skills": c.skill_proficiencies,
        "saves": c.saving_throw_proficiencies,
        "languages": c.languages,
        **vitals(c),
    }


def _spell(s: Spell) -> Json:
    details = [s.casting_time, str(s.range) if s.range else "", s.duration]
    return {
        "name": s.name,
        "level": s.level,
        "prepared": s.prepared,
        "details": " · ".join(d for d in details if d),
        "description": s.description,
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
