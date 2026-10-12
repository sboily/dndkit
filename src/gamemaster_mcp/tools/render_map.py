"""The battle map in words: a text grid, who stands where, what a move did.

The model never sees the drawn map, so these say what it needs to describe
the scene and rule on the next action: squares, distances, who is in reach.
"""

from gamemaster_mcp.game import battlefield, grid
from gamemaster_mcp.game.movement import Move
from gamemaster_mcp.models import Campaign, Combatant, GameState

KEYS = "abcdefghijklmnopqrstuvwxyz"


def battle_map(campaign: Campaign) -> str:
    """The grid (# wall, ~ difficult, a letter per combatant) and its legend."""
    state = campaign.game_state
    field = battlefield.require(state)
    walls, rough = battlefield.wall_squares(field), battlefield.difficult_squares(field)
    marks: dict[grid.Square, str] = {}
    legend = []
    for key, combatant in zip(KEYS, _placed(state), strict=False):
        for square in battlefield.footprint_of(state, combatant) or []:
            marks[square] = key
        side = "party" if battlefield.is_party(combatant) else "foe"
        size = "" if combatant.size == "medium" else f", {combatant.size}"
        legend.append(f"{key} {combatant.name} ({side}{size}) {combatant.position}")
    columns = [grid.name((x, 0))[0] for x in range(field.width)]
    rows = [
        f"{y + 1:>2} "
        + " ".join(
            marks.get((x, y), "#" if (x, y) in walls else "~" if (x, y) in rough else ".")
            for x in range(field.width)
        )
        for y in range(field.height)
    ]
    last = grid.name((field.width - 1, field.height - 1))
    lines = [
        f"Battle map A1-{last}, 5 ft squares. # wall, ~ difficult terrain.",
        "   " + " ".join(columns),
        *rows,
        "; ".join(legend) or "Nobody on the map yet: the fight's start places everyone.",
    ]
    away = [c.name for c in state.initiative_order if c.position is None]
    if away:
        lines.append(f"Not on the map: {', '.join(away)} (place_tokens).")
    return "\n".join(lines)


def positions(campaign: Campaign) -> str | None:
    """Who stands where, and how far the acting combatant is from the others."""
    state = campaign.game_state
    placed = _placed(state)
    if state.battlefield is None or not placed:
        return None
    line = "Positions: " + ", ".join(f"{c.name} {c.position}" for c in placed) + "."
    current = state.current_combatant
    if current is not None and current.position is not None:
        line += f" From {current.name}: {nearby(campaign, current)}."
    return line


def nearby(campaign: Campaign, combatant: Combatant) -> str:
    """The others by distance from *combatant*: "Goblin 1 adjacent, Ogre 30 ft"."""
    state = campaign.game_state
    mine = battlefield.footprint_of(state, combatant) or []
    distances = sorted(
        (grid.feet_between(mine, held), other.name)
        for other, held in battlefield.others(state, combatant)
    )
    return ", ".join(
        f"{name} {'adjacent' if feet == grid.FEET else f'{feet} ft'}" for feet, name in distances
    )


def move(campaign: Campaign, done: Move) -> str:
    """What a move did: where to, what it cost, who may strike, who is near now."""
    who = done.mover
    if done.forced:
        head = f"{who.name} is moved {done.feet} ft, {done.start} to {who.position}"
        return f"{head} (no movement spent, no opportunity attack). Now: {nearby(campaign, who)}."
    stood = " stands up and" if done.stood_up else ""
    text = (
        f"{who.name}{stood} moves {done.feet} ft, {done.start} to {who.position}; "
        f"{done.left} ft left this turn."
    )
    if done.provoked:
        text += (
            f" Leaving their reach provokes opportunity attacks from {', '.join(done.provoked)}."
        )
    if done.short_of is not None:
        target, feet = done.short_of
        text += f" {target} is still {feet} ft away."
    return f"{text} Now: {nearby(campaign, who)}."


def _placed(state: GameState) -> list[Combatant]:
    return [c for c in state.initiative_order if c.position is not None]
