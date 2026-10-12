"""Moving a combatant on the battle map by the 5e rules (PHB ch. 9).

A turn's movement is the creature's speed, doubled by Dash: 0 when grappled,
restrained, stunned, paralyzed, petrified or unconscious, halved from
exhaustion level 2 and 0 from level 5. A prone mover stands up first, for
half its speed. A move to a square the mover cannot afford is refused; a move
toward someone goes as far as it can. Forced movement (a shove, a spell)
spends nothing and provokes nothing.
"""

from dataclasses import dataclass

from gamemaster_mcp.errors import InvalidChangeError
from gamemaster_mcp.game import battlefield, combat, grid, pathing
from gamemaster_mcp.game.grid import Square
from gamemaster_mcp.game.pathing import Ground
from gamemaster_mcp.models import Campaign, Combatant

HALTED = {"grappled", "restrained", "paralyzed", "petrified", "stunned", "unconscious"}
DEFAULT_SPEED = 30


@dataclass(frozen=True)
class Move:
    """What a move did, for the model to narrate."""

    mover: Combatant
    start: str
    feet: int  # movement spent; for forced movement, distance moved
    left: int  # movement left this turn
    provoked: list[str]
    stood_up: bool = False
    forced: bool = False
    short_of: tuple[str, int] | None = None  # a creature still out of reach, and how far


@dataclass(frozen=True)
class Order:
    """Where a move goes: one of a square, toward someone, away from someone."""

    to: str | None = None
    toward: str | None = None
    away_from: str | None = None
    feet: int | None = None  # at most this far


def speed(campaign: Campaign, combatant: Combatant) -> int:
    """Walking speed now, conditions and exhaustion applied."""
    character = campaign.characters.get(combatant.character_id or "")
    if character is not None:
        base, conditions, exhaustion = character.speed, character.conditions, character.exhaustion
    else:
        base = combatant.speed if combatant.speed is not None else DEFAULT_SPEED
        conditions, exhaustion = combatant.conditions, 0
    if HALTED & set(conditions) or exhaustion >= 5:
        return 0
    return base // 2 if exhaustion >= 2 else base


def movement_left(campaign: Campaign, combatant: Combatant) -> int:
    """Feet of movement left this turn."""
    allowed = speed(campaign, combatant) * (2 if combatant.dashed else 1)
    return max(0, allowed - combatant.movement_used)


def move(
    campaign: Campaign, who: str, order: Order, dash: bool, disengage: bool, forced: bool
) -> Move:
    """Move *who* as *order* says; the combatant's square and movement are updated."""
    state = campaign.game_state
    mover = combat.find(state, who)
    start = battlefield.square_of(state, mover)
    if start is None:
        raise InvalidChangeError(f"{mover.name} is not on the map: place_tokens first.")
    if sum(target is not None for target in (order.to, order.toward, order.away_from)) != 1:
        raise InvalidChangeError("Say where: to a square, toward someone or away_from someone.")
    if forced:
        return _forced(campaign, mover, start, order)
    mover.dashed = mover.dashed or dash
    mover.disengaged = mover.disengaged or disengage
    stood_up = _stand_up(campaign, mover)
    if movement_left(campaign, mover) == 0:
        raise InvalidChangeError(_stuck(campaign, mover))
    ground = Ground(campaign, mover, provokes=not mover.disengaged)
    found = pathing.routes(ground, start)
    limit = movement_left(campaign, mover)
    if order.feet is not None:
        limit = min(limit, order.feet)
    end, short_of = _destination(campaign, ground, found, start, order, limit)
    route = pathing.path(found, end)
    mover.position = grid.name(end)
    mover.movement_used += found[end].feet
    return Move(
        mover=mover,
        start=grid.name(start),
        feet=found[end].feet,
        left=movement_left(campaign, mover),
        provoked=pathing.provoked_along(ground, route),
        stood_up=stood_up,
        short_of=short_of,
    )


def _destination(
    campaign: Campaign,
    ground: Ground,
    found: dict[Square, pathing.Route],
    start: Square,
    order: Order,
    limit: int,
) -> tuple[Square, tuple[str, int] | None]:
    if order.to is not None:
        return _to_square(ground, found, order.to, limit), None
    if order.toward is not None:
        return _toward(campaign, ground, found, start, order.toward, limit)
    away = _held(campaign, order.away_from or "")
    reachable = [s for s, r in found.items() if r.feet <= limit and ground.standable(s)]
    best = max(
        [start, *reachable],
        key=lambda s: (grid.steps_between(list(ground.squares(s)), away), -found[s].feet),
    )
    return best, None


def _to_square(ground: Ground, found: dict[Square, pathing.Route], to: str, limit: int) -> Square:
    target = grid.parse(to, ground.field)
    side = grid.SIZE_SQUARES[ground.mover.size]
    options = [
        (target[0] - dx, target[1] - dy)
        for dx in range(side)
        for dy in range(side)
        if (target[0] - dx, target[1] - dy) in found
        and ground.standable((target[0] - dx, target[1] - dy))
    ]
    name = ground.mover.name
    if not options:
        raise InvalidChangeError(f"{name} cannot get to {to.upper()}: it is blocked or taken.")
    best = min(options, key=lambda s: (found[s].feet, found[s].provocations))
    if found[best].feet > limit:
        raise InvalidChangeError(
            f"{to.upper()} is {found[best].feet} feet of movement away; {name} has {limit} left. "
            "Move toward it, or Dash."
        )
    return best


def _toward(
    campaign: Campaign,
    ground: Ground,
    found: dict[Square, pathing.Route],
    start: Square,
    toward: str,
    limit: int,
) -> tuple[Square, tuple[str, int] | None]:
    target = combat.find(campaign.game_state, toward)
    held = _held(campaign, toward)
    reach = max(ground.mover.reach, grid.FEET)

    def gap(s: Square) -> int:
        return grid.feet_between(list(ground.squares(s)), held)

    def _offset(s: Square) -> float:
        mine = list(ground.squares(s))
        return sum((_centre(mine, axis) - _centre(held, axis)) ** 2 for axis in (0, 1))

    if gap(start) <= reach:
        return start, None
    near = [s for s in found if ground.standable(s) and gap(s) <= reach]
    if near:  # cheapest first; of equals, the one facing the target squarely
        goal = min(near, key=lambda s: (found[s].feet, found[s].provocations, _offset(s)))
        if found[goal].feet <= limit:
            return goal, None
    else:  # walled off: head for the closest square there is
        goal = min(found, key=lambda s: (gap(s), found[s].feet))
    end = start
    for square in pathing.path(found, goal):
        if found[square].feet > limit:
            break
        if ground.standable(square):
            end = square
    return end, (target.name, gap(end))


def _stuck(campaign: Campaign, mover: Combatant) -> str:
    character = campaign.characters.get(mover.character_id or "")
    conditions = set(character.conditions if character else mover.conditions)
    halted = sorted(HALTED & conditions)
    if halted:
        return f"{mover.name} cannot move while {', '.join(halted)}."
    if speed(campaign, mover) == 0:
        return f"{mover.name} has a speed of 0."
    return f"{mover.name} has no movement left this turn (Dash doubles it)."


def _held(campaign: Campaign, name: str) -> list[Square]:
    state = campaign.game_state
    other = combat.find(state, name)
    held = battlefield.footprint_of(state, other)
    if held is None:
        raise InvalidChangeError(f"{other.name} is not on the map: place_tokens first.")
    return held


def _stand_up(campaign: Campaign, mover: Combatant) -> bool:
    character = campaign.characters.get(mover.character_id or "")
    conditions = character.conditions if character else mover.conditions
    if "prone" not in conditions:
        return False
    cost = speed(campaign, mover) // 2
    if speed(campaign, mover) == 0 or movement_left(campaign, mover) < cost:
        raise InvalidChangeError(f"{mover.name} is prone and lacks the movement to stand up.")
    mover.movement_used += cost
    standing = [c for c in conditions if c != "prone"]
    if character is not None:
        character.conditions = standing
    else:
        mover.conditions = standing
    return True


def _forced(campaign: Campaign, mover: Combatant, start: Square, order: Order) -> Move:
    ground = Ground(campaign, mover, provokes=False)
    if order.to is not None:
        end = grid.parse(order.to, ground.field)
        if not ground.standable(end):
            raise InvalidChangeError(f"{mover.name} cannot be put on {order.to.upper()}.")
    else:
        source = _held(campaign, order.away_from or order.toward or "")
        away = 1 if order.away_from is not None else -1
        end = _push(ground, start, source, away, (order.feet or grid.FEET) // grid.FEET)
    mover.position = grid.name(end)
    moved = grid.steps_between([start], [end]) * grid.FEET
    left = movement_left(campaign, mover)
    return Move(
        mover=mover, start=grid.name(start), feet=moved, left=left, provoked=[], forced=True
    )


def _push(ground: Ground, start: Square, source: list[Square], away: int, steps: int) -> Square:
    mine = list(ground.squares(start))
    dx, dy = (_sign(_centre(mine, axis) - _centre(source, axis)) * away for axis in (0, 1))
    if not (dx or dy):
        raise InvalidChangeError("They stand on the same spot: say where they go with to.")
    here = start
    for _ in range(steps):
        there = (here[0] + dx, here[1] + dy)
        if not ground.standable(there):  # a wall, the edge, or someone in the way
            break
        here = there
    return here


def _centre(squares: list[Square], axis: int) -> float:
    values = [s[axis] for s in squares]
    return (min(values) + max(values)) / 2


def _sign(value: float) -> int:
    return (value > 0) - (value < 0)
