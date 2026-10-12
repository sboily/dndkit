"""Areas of effect on the battle map (PHB ch. 10, DMG ch. 8 "Areas of Effect").

A sphere (a cylinder, seen from above) of radius R holds every square within
R feet of its centre square, measured as movement is. A cube of side S is
S/5 squares a side: centred on a square or a creature, or against its
caster's side facing the target. Cones and lines start at the edge of their
caster's space; a square is in when at least half of it is (DMG), and a cone
is as wide as it is far. Walls stop an area: a square is out when the line
from the area's origin to its centre crosses a wall. A creature is caught
when any square it holds is in.
"""

import math
import re
from dataclasses import dataclass
from typing import Literal

from gamemaster_mcp.errors import InvalidChangeError
from gamemaster_mcp.game import battlefield, combat, grid, sight
from gamemaster_mcp.game.grid import Square
from gamemaster_mcp.game.sight import Point
from gamemaster_mcp.models import Combatant, GameState

Shape = Literal["sphere", "cube", "cone", "line"]
SAMPLES = 4  # per side of a square, to measure how much of it an area covers
_SQUARE = re.compile(r"\s*[A-Za-z]\s*\d{1,2}\s*")


@dataclass(frozen=True)
class Spot:
    """Where an area is anchored: some squares, and the creature on them if any."""

    squares: list[Square]
    creature: Combatant | None


@dataclass(frozen=True)
class Area:
    """What an area of effect covers and who it catches."""

    label: str
    squares: list[Square]
    caught: list[Combatant]


@dataclass(frozen=True)
class Aim:
    """How an area is aimed, as a tool call describes it."""

    shape: Shape
    feet: int  # radius (sphere), side (cube), length (cone, line)
    at: str | None = None  # centre: a square or a creature
    source: str | None = None  # the caster, for a cone, a line or a cube against them
    toward: str | None = None  # where a cone, line or cube points
    width: int = grid.FEET  # a line's width


def resolve(state: GameState, aim: Aim) -> Area:
    """The area *aim* covers, drawn on the map until the next turn."""
    field = battlefield.require(state)
    walls = battlefield.wall_squares(field)
    if aim.shape in ("cone", "line") or (aim.shape == "cube" and aim.source):
        source, toward = _need(state, aim.source, "source"), _need(state, aim.toward, "toward")
        origin, squares = _from_caster(state, aim, source, toward)
        exclude = source
    else:
        centre = _need(state, aim.at, "at")
        origin = sight.centre(centre.squares)
        squares = (
            _sphere(state, centre, aim.feet) if aim.shape == "sphere" else _cube(centre, aim.feet)
        )
        exclude = Spot([], None)
    inside = [
        s
        for s in squares
        if grid.inside(s, field)
        and s not in walls
        and s not in exclude.squares
        and not sight.blocked(origin, sight.centre([s]), walls)
    ]
    held = set(inside)
    caught = [
        c
        for c, squares_held in _everyone(state)
        if c is not exclude.creature and held & set(squares_held)
    ]
    label = f"{aim.feet}-ft {aim.shape}"
    field.area, field.area_label = [grid.name(s) for s in inside], label
    return Area(label, inside, caught)


def _sphere(state: GameState, centre: Spot, feet: int) -> list[Square]:
    field = battlefield.require(state)
    every = [(x, y) for y in range(field.height) for x in range(field.width)]
    return [s for s in every if grid.feet_between([s], centre.squares) <= feet]


def _cube(centre: Spot, feet: int) -> list[Square]:
    side = max(1, feet // grid.FEET)
    xs = [x for x, _ in centre.squares]
    ys = [y for _, y in centre.squares]
    return [
        (x, y) for y in _span(min(ys), max(ys), 0, side) for x in _span(min(xs), max(xs), 0, side)
    ]


def _from_caster(
    state: GameState, aim: Aim, source: Spot, toward: Spot
) -> tuple[Point, list[Square]]:
    start, end = sight.centre(source.squares), sight.centre(toward.squares)
    dx, dy = end[0] - start[0], end[1] - start[1]
    if not (dx or dy):
        raise InvalidChangeError("The area points nowhere: aim it at another square.")
    if aim.shape == "cube":
        return start, _cube_against(source, dx, dy, aim.feet)
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    # The origin is where the line from the caster's centre leaves its space.
    half = (max(x for x, _ in source.squares) - min(x for x, _ in source.squares) + 1) * 2.5
    edge = half / max(abs(ux), abs(uy))
    origin = (start[0] + ux * edge, start[1] + uy * edge)
    field = battlefield.require(state)
    every = [(x, y) for y in range(field.height) for x in range(field.width)]
    covered = [s for s in every if _share(s, origin, (ux, uy), aim) >= 0.5]
    return origin, covered


def _cube_against(source: Spot, dx: float, dy: float, feet: int) -> list[Square]:
    side = max(1, feet // grid.FEET)
    xs = [x for x, _ in source.squares]
    ys = [y for _, y in source.squares]
    return [
        (x, y)
        for y in _span(min(ys), max(ys), dy, side)
        for x in _span(min(xs), max(xs), dx, side)
    ]


def _span(low: int, high: int, step: float, side: int) -> range:
    """*side* rows or columns: past *high* (step > 0), before *low* (< 0), or centred."""
    if step > 0:
        return range(high + 1, high + 1 + side)
    if step < 0:
        return range(low - side, low)
    first = low + (high - low + 1 - side) // 2
    return range(first, first + side)


def _share(square: Square, origin: Point, direction: Point, aim: Aim) -> float:
    """How much of *square* the cone or line covers, from 0 to 1."""
    inside = 0
    for i in range(SAMPLES):
        for j in range(SAMPLES):
            px = (square[0] + (i + 0.5) / SAMPLES) * grid.FEET - origin[0]
            py = (square[1] + (j + 0.5) / SAMPLES) * grid.FEET - origin[1]
            along = px * direction[0] + py * direction[1]
            across = abs(px * direction[1] - py * direction[0])
            limit = along / 2 if aim.shape == "cone" else aim.width / 2
            inside += 0 < along <= aim.feet and across <= limit
    return inside / SAMPLES**2


def _need(state: GameState, text: str | None, role: str) -> Spot:
    if not text:
        raise InvalidChangeError(f"This area needs {role}: a square like E5, or a creature.")
    if _SQUARE.fullmatch(text):
        return Spot([grid.parse(text, battlefield.require(state))], None)
    creature = combat.find(state, text)
    held = battlefield.footprint_of(state, creature)
    if held is None:
        raise InvalidChangeError(f"{creature.name} is not on the map.")
    return Spot(held, creature)


def _everyone(state: GameState) -> list[tuple[Combatant, list[Square]]]:
    placed = []
    for combatant in state.initiative_order:
        held = battlefield.footprint_of(state, combatant)
        if held is not None:
            placed.append((combatant, held))
    return placed
