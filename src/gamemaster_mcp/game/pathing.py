"""Routes across the battle map for one mover (PHB ch. 9, "Movement and Position").

Entering a square costs 5 feet, diagonals included, and 10 in difficult
terrain or in another creature's space. A mover passes through allies, and
through foes only when two sizes apart; it never ends a move on anyone, and
never squeezes diagonally between two walls. Leaving a foe's reach provokes
an opportunity attack unless the mover Disengaged or is moved by force; of
two routes as short, the one provoking fewer is taken.
"""

import heapq
from dataclasses import dataclass

from gamemaster_mcp.game import battlefield, grid
from gamemaster_mcp.game.grid import Square
from gamemaster_mcp.models import Campaign, Combatant

NO_REACTION = {"incapacitated", "paralyzed", "petrified", "stunned", "unconscious"}
DIRECTIONS = [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy]


@dataclass(frozen=True)
class Other:
    """Another creature on the map, as the mover meets it."""

    combatant: Combatant
    squares: frozenset[Square]
    passable: bool  # the mover may cross its space
    threat_reach: int | None  # feet of reach in which leaving provokes; None: never


@dataclass(frozen=True)
class Route:
    """The cheapest way found to a square."""

    feet: int
    provocations: int
    previous: Square | None


class Ground:
    """The map as one mover sees it: walls, difficult terrain, the others."""

    def __init__(
        self, campaign: Campaign, mover: Combatant, provokes: bool, as_players_see: bool = False
    ) -> None:
        state = campaign.game_state
        self.field = battlefield.require(state)
        self.walls = battlefield.wall_squares(self.field)
        self.difficult = battlefield.difficult_squares(self.field)
        self.mover = mover
        self.others = [
            _meet(campaign, mover, other, held, provokes)
            for other, held in battlefield.others(state, mover)
            # The players' screens must not give a hidden foe away by a hole in the map.
            if not (as_players_see and other.hidden and not battlefield.is_party(other))
        ]

    def squares(self, top_left: Square) -> frozenset[Square]:
        """What the mover holds standing at *top_left*."""
        return frozenset(grid.footprint(top_left, self.mover.size))

    def crossable(self, top_left: Square) -> bool:
        """Whether the mover may pass through *top_left*."""
        held = self.squares(top_left)
        if any(not grid.inside(s, self.field) or s in self.walls for s in held):
            return False
        return all(o.passable or not held & o.squares for o in self.others)

    def standable(self, top_left: Square) -> bool:
        """Whether the mover may end its move at *top_left*."""
        held = self.squares(top_left)
        return self.crossable(top_left) and not any(held & o.squares for o in self.others)

    def step_feet(self, top_left: Square) -> int:
        """What entering *top_left* costs."""
        held = self.squares(top_left)
        crowded = any(held & o.squares for o in self.others)
        return 2 * grid.FEET if crowded or held & self.difficult else grid.FEET

    def provoked(self, here: Square, there: Square) -> list[Combatant]:
        """The foes whose reach the step from *here* to *there* leaves."""
        before, after = list(self.squares(here)), list(self.squares(there))
        return [
            o.combatant
            for o in self.others
            if o.threat_reach is not None
            and grid.feet_between(before, list(o.squares)) <= o.threat_reach
            and grid.feet_between(after, list(o.squares)) > o.threat_reach
        ]

    def cuts_corner(self, here: Square, there: Square) -> bool:
        """A diagonal step between two blocked squares."""
        (x1, y1), (x2, y2) = here, there
        if x1 == x2 or y1 == y2:
            return False
        return not self.crossable((x2, y1)) and not self.crossable((x1, y2))


def routes(ground: Ground, start: Square) -> dict[Square, Route]:
    """The cheapest route to every square the mover can reach (Dijkstra)."""
    best = {start: Route(0, 0, None)}
    queue = [(0, 0, start)]
    while queue:
        feet, provocations, here = heapq.heappop(queue)
        if (feet, provocations) > (best[here].feet, best[here].provocations):
            continue
        for dx, dy in DIRECTIONS:
            there = (here[0] + dx, here[1] + dy)
            if not ground.crossable(there) or ground.cuts_corner(here, there):
                continue
            cost = (
                feet + ground.step_feet(there),
                provocations + len(ground.provoked(here, there)),
            )
            known = best.get(there)
            if known is None or cost < (known.feet, known.provocations):
                best[there] = Route(cost[0], cost[1], here)
                heapq.heappush(queue, (cost[0], cost[1], there))
    return best


def path(found: dict[Square, Route], end: Square) -> list[Square]:
    """The squares from the start to *end*, both included."""
    squares = [end]
    while (previous := found[squares[-1]].previous) is not None:
        squares.append(previous)
    return squares[::-1]


def provoked_along(ground: Ground, squares: list[Square]) -> list[str]:
    """Who gets an opportunity attack along *squares*, each named once."""
    names: list[str] = []
    for here, there in zip(squares, squares[1:], strict=False):
        names += [c.name for c in ground.provoked(here, there) if c.name not in names]
    return names


def _meet(
    campaign: Campaign, mover: Combatant, other: Combatant, held: list[Square], provokes: bool
) -> Other:
    hostile = battlefield.is_party(other) != battlefield.is_party(mover)
    apart = abs(grid.SIZE_RANK[other.size] - grid.SIZE_RANK[mover.size]) >= 2
    reacts = provokes and hostile and can_react(campaign, other)
    return Other(other, frozenset(held), not hostile or apart, other.reach if reacts else None)


def can_react(campaign: Campaign, combatant: Combatant) -> bool:
    """Whether *combatant* can take a reaction: conscious, not incapacitated."""
    character = campaign.characters.get(combatant.character_id or "")
    conditions = set(character.conditions if character else combatant.conditions)
    hit_points = character.hit_points_current if character else combatant.hit_points
    return not conditions & NO_REACTION and hit_points != 0
