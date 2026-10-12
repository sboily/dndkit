"""Lines across the battle map: what stops an area of effect, and cover.

Points are in feet, the map's top-left corner at (0, 0): square (x, y) spans
5x to 5x+5 across and 5y to 5y+5 down. A line along a square's edge or
through its corner passes; one crossing its inside is blocked.

Cover follows the DMG (ch. 8, "Cover" on a grid): from the attacker's best
corner, lines to the four corners of the target's square; one or two blocked
by an obstacle give half cover, three or four three-quarters, and a target
walled off from every corner has total cover. Creatures in the way give half
cover at most.
"""

import math
from collections.abc import Iterable
from dataclasses import dataclass

from dndkit.errors import InvalidChangeError
from dndkit.game import battlefield, combat, grid, pathing
from dndkit.game.grid import Square
from dndkit.models import Campaign, Combatant, GameState

Point = tuple[float, float]
EDGE = 0.01  # how far inside a square a line must go to be blocked
COVER = ("none", "half", "three-quarters", "total")
COVER_BONUS = {"half": 2, "three-quarters": 5}
_SIDES = ((-1, 0), (1, 0), (0, -1), (0, 1))  # left, right, top, bottom


def centre(squares: Iterable[Square]) -> Point:
    """The middle of the squares, in feet."""
    held = list(squares)
    xs = [x for x, _ in held]
    ys = [y for _, y in held]
    return ((min(xs) + max(xs) + 1) * grid.FEET / 2, (min(ys) + max(ys) + 1) * grid.FEET / 2)


def corners(square: Square) -> list[Point]:
    """A square's four corners, in feet."""
    x, y = square[0] * grid.FEET, square[1] * grid.FEET
    return [(x, y), (x + grid.FEET, y), (x, y + grid.FEET), (x + grid.FEET, y + grid.FEET)]


def crosses(
    a: Point, b: Point, square: Square, solid: set[Square] | frozenset[Square] = frozenset()
) -> bool:
    """Whether the segment a-b goes through the inside of *square* (Liang-Barsky).

    A side shared with another *solid* square is no edge: a line running along
    the seam between two wall squares is inside the wall.
    """
    x, y = square
    inset = [EDGE if (x + dx, y + dy) not in solid else -EDGE for dx, dy in _SIDES]
    x0, x1 = x * grid.FEET + inset[0], (x + 1) * grid.FEET - inset[1]
    y0, y1 = y * grid.FEET + inset[2], (y + 1) * grid.FEET - inset[3]
    dx, dy = b[0] - a[0], b[1] - a[1]
    start, end = 0.0, 1.0
    for p, q in ((-dx, a[0] - x0), (dx, x1 - a[0]), (-dy, a[1] - y0), (dy, y1 - a[1])):
        if p == 0:
            if q < 0:
                return False
            continue
        t = q / p
        if p < 0:
            start = max(start, t)
        else:
            end = min(end, t)
        if start > end:
            return False
    return True


def blocked(a: Point, b: Point, obstacles: set[Square]) -> bool:
    """Whether any of *obstacles* stands across the segment a-b."""
    left, right = sorted((a[0], b[0]))
    top, bottom = sorted((a[1], b[1]))
    columns = range(math.floor(left / grid.FEET) - 1, math.floor(right / grid.FEET) + 2)
    rows = range(math.floor(top / grid.FEET) - 1, math.floor(bottom / grid.FEET) + 2)
    return any(
        (x, y) in obstacles and crosses(a, b, (x, y), obstacles) for x in columns for y in rows
    )


def cover(state: GameState, attacker: Combatant, target: Combatant) -> str:
    """The cover *target* has against *attacker*: none, half, three-quarters or total."""
    walls = battlefield.wall_squares(battlefield.require(state))
    mine = battlefield.footprint_of(state, attacker) or []
    theirs = battlefield.footprint_of(state, target) or []
    bodies = {
        s
        for other, held in battlefield.others(state, attacker)
        if other is not target
        for s in held
    }
    best = len(COVER) - 1
    for corner in {point for square in mine for point in corners(square)}:
        for square in theirs:
            lines = [(corner, end) for end in corners(square)]
            by_walls = sum(blocked(a, b, walls) for a, b in lines)
            by_bodies = any(blocked(a, b, bodies) for a, b in lines)
            if by_walls == 4:
                level = 3
            elif by_walls >= 3:
                level = 2
            else:
                level = 1 if by_walls or by_bodies else 0
            best = min(best, level)
    return COVER[best]


@dataclass(frozen=True)
class Sightline:
    """What bears on an attack from one combatant at another."""

    attacker: Combatant
    target: Combatant
    feet: int
    cover: str
    in_reach: bool
    pressed_by: list[str]  # foes adjacent to the attacker: its ranged attacks have disadvantage


def look(campaign: Campaign, attacker_name: str, target_name: str) -> Sightline:
    """Distance, cover and what else bears on *attacker_name* attacking *target_name*."""
    state = campaign.game_state
    attacker = combat.find(state, attacker_name)
    target = combat.find(state, target_name)
    mine = battlefield.footprint_of(state, attacker)
    theirs = battlefield.footprint_of(state, target)
    if mine is None or theirs is None:
        raise InvalidChangeError("Both must be on the map: place_tokens first.")
    feet = grid.feet_between(mine, theirs)
    pressed = [
        other.name
        for other, held in battlefield.others(state, attacker)
        if battlefield.is_party(other) != battlefield.is_party(attacker)
        and grid.feet_between(mine, held) <= grid.FEET
        and pathing.can_react(campaign, other)
    ]
    return Sightline(
        attacker, target, feet, cover(state, attacker, target), feet <= attacker.reach, pressed
    )
