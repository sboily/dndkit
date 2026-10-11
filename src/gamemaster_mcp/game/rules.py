"""D&D 5e rules the tools apply: hit points and experience."""

from dataclasses import dataclass


@dataclass(frozen=True)
class HitPoints:
    """Hit points after a change."""

    current: int
    temporary: int


def apply_hp_change(current: int, maximum: int, temporary: int, delta: int) -> HitPoints:
    """Healing up to the maximum, or damage taken from temporary hit points first.

    Healing never restores temporary hit points (PHB, "Temporary Hit Points").
    """
    if delta >= 0:
        return HitPoints(current=min(maximum, current + delta), temporary=temporary)
    damage = -delta
    absorbed = min(temporary, damage)
    return HitPoints(current=max(0, current - (damage - absorbed)), temporary=temporary - absorbed)


def experience_per_character(total_xp: int, party_size: int) -> int:
    """XP each character earns: the monsters' total XP split evenly (DMG, ch. 3).

    The DMG's encounter multipliers rate an encounter's difficulty; they never
    change the XP awarded.
    """
    if party_size < 1:
        raise ValueError("party_size must be at least 1")
    return total_xp // party_size
