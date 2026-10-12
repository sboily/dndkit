"""Squares on a battle map: names like "D7", areas, footprints and distances.

Columns are letters from A, rows numbers from 1, A1 at the top left. Every
square is 5 feet and, as in the Player's Handbook ("Playing on a Grid"), a
diagonal step costs 5 feet like any other, so two squares are as many steps
apart as the larger of their column and row differences.
"""

import re

from dndkit.errors import InvalidChangeError
from dndkit.models import Battlefield, Size

FEET = 5
Square = tuple[int, int]  # column, row; both from 0

# Squares a side: Tiny and Small creatures still hold a whole square here.
SIZE_SQUARES: dict[str, int] = {
    "tiny": 1,
    "small": 1,
    "medium": 1,
    "large": 2,
    "huge": 3,
    "gargantuan": 4,
}
SIZE_RANK: dict[str, int] = {size: rank for rank, size in enumerate(SIZE_SQUARES)}

_NAME = re.compile(r"([A-Za-z])\s*(\d{1,2})")


def name(square: Square) -> str:
    """ "D7" for (3, 6)."""
    column, row = square
    return f"{chr(ord('A') + column)}{row + 1}"


def parse(text: str, field: Battlefield) -> Square:
    """The square *text* names ("d7", "D 7"), checked against the map's edges."""
    match = _NAME.fullmatch(text.strip())
    if match is None:
        raise InvalidChangeError(f"'{text}' is not a square: write a column letter and a row, D7.")
    square = (ord(match.group(1).upper()) - ord("A"), int(match.group(2)) - 1)
    if not inside(square, field):
        last = name((field.width - 1, field.height - 1))
        raise InvalidChangeError(f"{name(square)} is off the map, which runs from A1 to {last}.")
    return square


def area(text: str, field: Battlefield) -> list[Square]:
    """The squares *text* names: one ("C3") or a rectangle between two corners ("C1:E2")."""
    corners = [parse(part, field) for part in text.split(":")]
    if len(corners) > 2:
        raise InvalidChangeError(f"'{text}' has more than two corners.")
    (x1, y1), (x2, y2) = corners[0], corners[-1]
    return [
        (x, y)
        for y in range(min(y1, y2), max(y1, y2) + 1)
        for x in range(min(x1, x2), max(x1, x2) + 1)
    ]


def inside(square: Square, field: Battlefield) -> bool:
    """Whether *square* is on the map."""
    column, row = square
    return 0 <= column < field.width and 0 <= row < field.height


def footprint(top_left: Square, size: Size) -> list[Square]:
    """The squares a creature of *size* holds from *top_left*."""
    side = SIZE_SQUARES[size]
    x, y = top_left
    return [(x + dx, y + dy) for dy in range(side) for dx in range(side)]


def steps_between(a: list[Square], b: list[Square]) -> int:
    """Steps between the nearest squares of two footprints: 1 when adjacent, 0 when they meet."""
    dx = max(
        0, min(x for x, _ in b) - max(x for x, _ in a), min(x for x, _ in a) - max(x for x, _ in b)
    )
    dy = max(
        0, min(y for _, y in b) - max(y for _, y in a), min(y for _, y in a) - max(y for _, y in b)
    )
    return max(dx, dy)


def feet_between(a: list[Square], b: list[Square]) -> int:
    """Distance in feet between two footprints, as 5e measures it on a grid."""
    return steps_between(a, b) * FEET
