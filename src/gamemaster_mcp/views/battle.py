"""The battle map as the screens draw it: terrain, tokens, where the actor can go.

The game master's screens get exact hit points; the players' get how hurt a
foe looks, and see where a creature can move only on their own side's turns.
"""

from gamemaster_mcp.game import battlefield, grid, movement, pathing
from gamemaster_mcp.models import Campaign, Combatant

Json = dict[str, object]


def health(hit_points: int | None, maximum: int | None) -> str | None:
    """How hurt a creature looks: unhurt, hurt, bloodied (half or less) or down."""
    if hit_points is None or not maximum:
        return None
    if hit_points <= 0:
        return "down"
    if hit_points >= maximum:
        return "unhurt"
    return "bloodied" if hit_points * 2 <= maximum else "hurt"


def battle_map(campaign: Campaign, public: bool) -> Json | None:
    """The map for drawing, or None when the fight has none."""
    state = campaign.game_state
    field = state.battlefield
    if field is None:
        return None
    current = state.current_combatant
    tokens = [
        _token(campaign, c, c is current, public)
        for c in state.initiative_order
        if c.position is not None and not (public and unseen(c))
    ]
    shows_moves = current is not None and (not public or battlefield.is_party(current))
    return {
        "width": field.width,
        "height": field.height,
        "walls": [list(s) for s in sorted(battlefield.wall_squares(field))],
        "difficult": [list(s) for s in sorted(battlefield.difficult_squares(field))],
        "area": [list(grid.parse(s, field)) for s in field.area],
        "area_label": field.area_label,
        "tokens": tokens,
        "moves": _moves(campaign, current, public) if shows_moves and current else [],
    }


def unseen(combatant: Combatant) -> bool:
    """A foe hidden from the players: kept off their screens altogether."""
    return combatant.hidden and not battlefield.is_party(combatant)


def _token(campaign: Campaign, combatant: Combatant, current: bool, public: bool) -> Json:
    x, y = battlefield.square_of(campaign.game_state, combatant) or (0, 0)
    character = campaign.characters.get(combatant.character_id or "")
    hp: int | None
    hp_max: int | None
    if character is not None:
        hp, hp_max = character.hit_points_current, character.hit_points_max
    else:
        hp, hp_max = combatant.hit_points, combatant.hit_points_max
    token: Json = {
        "name": combatant.name,
        "x": x,
        "y": y,
        "size": grid.SIZE_SQUARES[combatant.size],
        "party": battlefield.is_party(combatant),
        "current": current,
        "down": hp == 0,
        "hidden": combatant.hidden,
        "boss": combatant.boss,
    }
    if public and character is None:
        token["health"] = health(hp, hp_max)
    else:
        token.update(hp=hp, hp_max=hp_max)
    return token


def _moves(campaign: Campaign, mover: Combatant, public: bool) -> list[list[int]]:
    """The squares *mover* can still reach this turn."""
    start = battlefield.square_of(campaign.game_state, mover)
    left = movement.movement_left(campaign, mover)
    if start is None or left == 0:
        return []
    ground = pathing.Ground(campaign, mover, provokes=False, as_players_see=public)
    return [
        list(square)
        for square, route in pathing.routes(ground, start).items()
        if 0 < route.feet <= left and ground.standable(square)
    ]
