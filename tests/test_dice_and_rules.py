"""Dice notation and the 5e rules the tools apply."""

import random

import pytest

from gamemaster_mcp.errors import DiceError
from gamemaster_mcp.game import dice, rules


def seeded() -> random.Random:
    return random.Random(7)


@pytest.mark.parametrize(
    ("notation", "terms"),
    [
        ("d20", [(1, 1, 20)]),
        ("1d20+5", [(1, 1, 20), (1, 5, 0)]),
        ("1d20 + 5", [(1, 1, 20), (1, 5, 0)]),
        ("2d6+1d4-1", [(1, 2, 6), (1, 1, 4), (-1, 1, 0)]),
        ("4D6", [(1, 4, 6)]),
    ],
)
def test_parse_accepts_spoken_forms(notation: str, terms: list[tuple[int, int, int]]) -> None:
    assert [(t.sign, t.count, t.sides) for t in dice.parse(notation)] == terms


@pytest.mark.parametrize(
    "notation",
    ["", "5", "0d6", "1d0", "1d1", "1d20abc", "1d20 5", "101d6", "60d6+60d6", "d20+5000"],
)
def test_parse_refuses_bad_or_huge_notation(notation: str) -> None:
    with pytest.raises(DiceError):
        dice.parse(notation)


def test_roll_keeps_the_modifier_and_sums_terms() -> None:
    result = dice.roll("1d20 + 5", rng=seeded())
    rolled = random.Random(7).randint(1, 20)
    assert result.total == rolled + 5
    assert result.detail.endswith(f"= {rolled + 5}")


def test_advantage_keeps_the_higher_d20() -> None:
    expected = random.Random(7)
    first, second = expected.randint(1, 20), expected.randint(1, 20)
    result = dice.roll("d20+2", advantage=True, rng=seeded())
    assert result.total == max(first, second) + 2


def test_advantage_and_disadvantage_cancel_out() -> None:
    result = dice.roll("d20", advantage=True, disadvantage=True, rng=seeded())
    assert "cancel out" in result.detail
    assert result.total == random.Random(7).randint(1, 20)


def test_advantage_needs_a_single_d20() -> None:
    with pytest.raises(DiceError, match="one d20"):
        dice.roll("2d6", advantage=True)


def test_damage_hits_temporary_hit_points_first() -> None:
    assert rules.apply_hp_change(10, 10, 3, -5) == rules.HitPoints(current=8, temporary=0)
    assert rules.apply_hp_change(10, 10, 6, -5) == rules.HitPoints(current=10, temporary=1)
    assert rules.apply_hp_change(4, 10, 0, -9) == rules.HitPoints(current=0, temporary=0)


def test_healing_stops_at_max_and_keeps_temporary() -> None:
    assert rules.apply_hp_change(4, 10, 2, 20) == rules.HitPoints(current=10, temporary=2)


def test_experience_is_split_evenly_without_multiplier() -> None:
    assert rules.experience_per_character(900, 2) == 450
    assert rules.experience_per_character(900, 6) == 150
