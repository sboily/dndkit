"""The battle map of the running fight: its terrain, and who stands where.

Combatants keep their own square (``Combatant.position``, the top-left one
for a creature bigger than a square). Whoever has none when the map is laid
out or the fight starts is placed at an edge: the party on the left, its
foes on the right.
"""

from collections.abc import Iterable, Sequence

from gamemaster_mcp.errors import InvalidChangeError
from gamemaster_mcp.game import grid
from gamemaster_mcp.game.grid import Square
from gamemaster_mcp.models import Battlefield, Combatant, GameState


def require(state: GameState) -> Battlefield:
    """The map, or an error saying how to lay one out."""
    if state.battlefield is None:
        raise InvalidChangeError(
            "There is no battle map: lay one out with set_battlefield, "
            "or keep describing positions in words."
        )
    return state.battlefield


def build(width: int, height: int, walls: Iterable[str], difficult: Iterable[str]) -> Battlefield:
    """A map with its terrain squares checked and listed one by one."""
    field = Battlefield(width=width, height=height)
    blocked = _names(field, walls)
    field.walls = blocked
    field.difficult = [s for s in _names(field, difficult) if s not in blocked]
    return field


def lay_out(
    state: GameState, width: int, height: int, walls: Iterable[str], difficult: Iterable[str]
) -> list[Combatant]:
    """Replace the map; returns those who lost their square (off the map, in a wall)."""
    state.battlefield = build(width, height, walls, difficult)
    return settle(state)


def settle(state: GameState) -> list[Combatant]:
    """Take off the map whoever stands off it, in a wall or on someone placed before."""
    field = require(state)
    walls = wall_squares(field)
    taken: set[Square] = set()
    displaced = []
    for combatant in state.initiative_order:
        if combatant.position is None:
            continue
        try:
            held = set(footprint_of(state, combatant) or [])
        except InvalidChangeError:  # off the map
            held = set()
        if not held or held & (walls | taken) or any(not grid.inside(s, field) for s in held):
            combatant.position = None
            displaced.append(combatant)
            continue
        combatant.position = grid.name(min(held, key=lambda s: (s[1], s[0])))  # "d 7" -> "D7"
        taken |= held
    return displaced


def is_party(combatant: Combatant) -> bool:
    """Whether *combatant* fights on the party's side."""
    return combatant.character_id is not None or combatant.ally


def square_of(state: GameState, combatant: Combatant) -> Square | None:
    """The top-left square *combatant* stands on, if it has one on the map."""
    if combatant.position is None or state.battlefield is None:
        return None
    return grid.parse(combatant.position, state.battlefield)


def footprint_of(state: GameState, combatant: Combatant) -> list[Square] | None:
    """The squares *combatant* holds, if it is on the map."""
    top_left = square_of(state, combatant)
    return None if top_left is None else grid.footprint(top_left, combatant.size)


def free(state: GameState, mover: Combatant, top_left: Square) -> bool:
    """Whether *mover* can stand at *top_left*: on the map, off walls, alone."""
    field = require(state)
    squares = grid.footprint(top_left, mover.size)
    walls = wall_squares(field)
    if any(not grid.inside(s, field) or s in walls for s in squares):
        return False
    return not any(set(squares) & set(held) for _, held in others(state, mover))


def others(state: GameState, mover: Combatant) -> list[tuple[Combatant, list[Square]]]:
    """Every other combatant on the map, with the squares it holds."""
    placed = []
    for combatant in state.initiative_order:
        held = None if combatant is mover else footprint_of(state, combatant)
        if held is not None:
            placed.append((combatant, held))
    return placed


def place(state: GameState, combatant: Combatant, square: str) -> None:
    """Put *combatant* on *square* (its top-left one), which must be free."""
    top_left = grid.parse(square, require(state))
    if not free(state, combatant, top_left):
        raise InvalidChangeError(
            f"{combatant.name} cannot stand on {grid.name(top_left)}: "
            "a wall, the map's edge or someone else is in the way."
        )
    combatant.position = grid.name(top_left)


def place_the_rest(state: GameState) -> list[Combatant]:
    """Place everyone still off the map at their side's edge; returns who was placed."""
    if state.battlefield is None:
        return []
    placed = []
    for combatant in state.initiative_order:
        if combatant.position is None and _place_at_edge(state, combatant):
            placed.append(combatant)
    return placed


def wall_squares(field: Battlefield) -> set[Square]:
    """The blocked squares."""
    return {grid.parse(s, field) for s in field.walls}


def difficult_squares(field: Battlefield) -> set[Square]:
    """The squares of difficult terrain."""
    return {grid.parse(s, field) for s in field.difficult}


def _place_at_edge(state: GameState, combatant: Combatant) -> bool:
    field = require(state)
    side = grid.SIZE_SQUARES[combatant.size]
    columns: Sequence[int] = range(field.width - side + 1)
    if not is_party(combatant):
        columns = list(reversed(columns))
    middle = (field.height - side) / 2
    rows = sorted(range(field.height - side + 1), key=lambda row: abs(row - middle))
    for column in columns:
        for row in rows:
            if free(state, combatant, (column, row)):
                combatant.position = grid.name((column, row))
                return True
    return False


def _names(field: Battlefield, areas: Iterable[str]) -> list[str]:
    squares = {square for text in areas for square in grid.area(text, field)}
    return [grid.name(s) for s in sorted(squares, key=lambda s: (s[1], s[0]))]
