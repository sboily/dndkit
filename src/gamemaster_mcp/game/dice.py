"""Dice notation: parse "2d6+1d4+3" or "d20 - 1" and roll it."""

import random
import re
import secrets
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
class RollResult:
    """What was rolled and the total, as one line to read out."""

    notation: str
    total: int
    detail: str


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
    total = 0
    parts: list[str] = []
    for term in terms:
        value, shown = _roll_term(term, rng, mode)
        total += term.sign * value
        sign = "-" if term.sign < 0 else "+"
        parts.append(f"{sign} {shown}" if parts or term.sign < 0 else shown)
    detail = " ".join(parts)
    if advantage and disadvantage:
        detail += " (advantage and disadvantage cancel out)"
    return RollResult(notation=notation.strip(), total=total, detail=f"{detail} = {total}")


def _mode(terms: list[DiceTerm], notation: str, advantage: bool, disadvantage: bool) -> str:
    if advantage == disadvantage:
        return "normal"
    dice = [term for term in terms if term.sides]
    if len(dice) != 1 or dice[0].count != 1 or dice[0].sides != 20:
        raise DiceError(f"Advantage and disadvantage apply to one d20, not '{notation}'.")
    return "advantage" if advantage else "disadvantage"


def _roll_term(term: DiceTerm, rng: random.Random, mode: str) -> tuple[int, str]:
    if not term.sides:
        return term.count, str(term.count)
    if mode != "normal":
        first, second = rng.randint(1, 20), rng.randint(1, 20)
        kept = max(first, second) if mode == "advantage" else min(first, second)
        return kept, f"d20 {mode} [{first}, {second}] keeps {kept}"
    rolls = [rng.randint(1, term.sides) for _ in range(term.count)]
    return sum(rolls), f"{term.count}d{term.sides} [{', '.join(map(str, rolls))}]"
