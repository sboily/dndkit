"""Dice notation: parse "2d6+1d4+3" or "d20 - 1" and roll it."""

import itertools
import random
import re
import secrets
import threading
import time
from collections import deque
from dataclasses import dataclass

from gamemaster_mcp.errors import DiceError

MAX_DICE = 100
MAX_SIDES = 1000
MAX_CONSTANT = 1000
_EXAMPLES = "Use forms like d20, 1d20+5, 2d6+1d4+3 or 4d6-1."
_TERM = re.compile(r"\s*([+-])?\s*(?:(\d*)\s*d\s*(\d+)|(\d+))\s*", re.IGNORECASE)
_SYSTEM_RNG = secrets.SystemRandom()


@dataclass(frozen=True)
class DiceTerm:
    """``count`` dice of ``sides`` faces, or a constant when ``sides`` is 0."""

    sign: int
    count: int
    sides: int


@dataclass(frozen=True)
class RolledTerm:
    """One term as rolled: every die's face, or the constant (``sides`` 0).

    With advantage or disadvantage the term holds both d20 and ``kept`` says
    which value counts.
    """

    sign: int
    sides: int
    faces: tuple[int, ...]
    kept: int | None = None

    @property
    def value(self) -> int:
        """What the term adds to the total, before its sign."""
        return self.kept if self.kept is not None else sum(self.faces)


@dataclass(frozen=True)
class RollResult:
    """What was rolled: the line to read out, and every die for an animation."""

    notation: str
    total: int
    detail: str
    mode: str  # normal, advantage, disadvantage
    terms: tuple[RolledTerm, ...]


def parse(notation: str) -> list[DiceTerm]:
    """The terms of *notation*; raises ``DiceError`` on anything else."""
    text = notation.strip()
    terms: list[DiceTerm] = []
    position = 0
    while position < len(text):
        match = _TERM.match(text, position)
        if match is None or match.end() == position or (terms and match.group(1) is None):
            raise DiceError(f"Invalid dice notation '{notation}'. {_EXAMPLES}")
        terms.append(_term(match, notation))
        position = match.end()
    if not any(term.sides for term in terms):
        raise DiceError(f"'{notation}' has no dice. {_EXAMPLES}")
    if sum(term.count for term in terms if term.sides) > MAX_DICE:
        raise DiceError(f"'{notation}' rolls more than {MAX_DICE} dice.")
    return terms


def _term(match: re.Match[str], notation: str) -> DiceTerm:
    sign = -1 if match.group(1) == "-" else 1
    if match.group(4) is not None:
        constant = int(match.group(4))
        if constant > MAX_CONSTANT:
            raise DiceError(f"'{notation}': modifiers go up to {MAX_CONSTANT}.")
        return DiceTerm(sign, constant, 0)
    count = int(match.group(2) or 1)
    sides = int(match.group(3))
    if not 1 <= count <= MAX_DICE:
        raise DiceError(f"'{notation}': roll between 1 and {MAX_DICE} dice.")
    if not 2 <= sides <= MAX_SIDES:
        raise DiceError(f"'{notation}': dice have between 2 and {MAX_SIDES} sides.")
    return DiceTerm(sign, count, sides)


def roll(
    notation: str,
    *,
    advantage: bool = False,
    disadvantage: bool = False,
    rng: random.Random | None = None,
) -> RollResult:
    """Roll *notation*; advantage and disadvantage apply to a single d20."""
    terms = parse(notation)
    rng = rng or _SYSTEM_RNG
    mode = _mode(terms, notation, advantage, disadvantage)
    rolled = tuple(_roll_term(term, rng, mode) for term in terms)
    total = sum(term.sign * term.value for term in rolled)
    parts: list[str] = []
    for term in rolled:
        shown = _describe(term, mode)
        sign = "-" if term.sign < 0 else "+"
        parts.append(f"{sign} {shown}" if parts or term.sign < 0 else shown)
    detail = " ".join(parts)
    if advantage and disadvantage:
        detail += " (advantage and disadvantage cancel out)"
    return RollResult(
        notation=notation.strip(),
        total=total,
        detail=f"{detail} = {total}",
        mode=mode,
        terms=rolled,
    )


def _mode(terms: list[DiceTerm], notation: str, advantage: bool, disadvantage: bool) -> str:
    if advantage == disadvantage:
        return "normal"
    dice = [term for term in terms if term.sides]
    if len(dice) != 1 or dice[0].count != 1 or dice[0].sides != 20:
        raise DiceError(f"Advantage and disadvantage apply to one d20, not '{notation}'.")
    return "advantage" if advantage else "disadvantage"


def _roll_term(term: DiceTerm, rng: random.Random, mode: str) -> RolledTerm:
    if not term.sides:
        return RolledTerm(term.sign, 0, (term.count,))
    if mode != "normal":
        faces = (rng.randint(1, 20), rng.randint(1, 20))
        kept = max(faces) if mode == "advantage" else min(faces)
        return RolledTerm(term.sign, 20, faces, kept)
    return RolledTerm(
        term.sign, term.sides, tuple(rng.randint(1, term.sides) for _ in range(term.count))
    )


def _describe(term: RolledTerm, mode: str) -> str:
    if not term.sides:
        return str(term.faces[0])
    if term.kept is not None:
        return f"d20 {mode} [{term.faces[0]}, {term.faces[1]}] keeps {term.kept}"
    return f"{len(term.faces)}d{term.sides} [{', '.join(map(str, term.faces))}]"


class DiceLog:
    """The last rolls of this session, for the dice app to show; never saved."""

    def __init__(self, size: int = 20) -> None:
        self._rolls: deque[tuple[int, float, RollResult]] = deque(maxlen=size)
        self._counter = itertools.count(1)
        self._lock = threading.Lock()

    def record(self, result: RollResult) -> int:
        """Keep *result*; returns its sequence number."""
        with self._lock:
            number = next(self._counter)
            self._rolls.append((number, time.time(), result))
            return number

    def recent(self) -> list[tuple[int, float, RollResult]]:
        """(number, unix time, result), oldest first."""
        with self._lock:
            return list(self._rolls)
