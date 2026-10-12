"""The fight as the game master sees it, in the MCP widget and the web backstage.

Monsters' exact hit points, hidden foes and legendary uses show here; what
the players may see is built separately, field by field, in ``views.public``
and ``views.everyone``.
"""

from gamemaster_mcp.models import Campaign, Combatant
from gamemaster_mcp.views.battle import battle_map
from gamemaster_mcp.views.everyone import Json, vitals


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
        "last": (
            state.last_combat.model_dump(mode="json")
            if state.last_combat and not state.in_combat
            else None
        ),
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
