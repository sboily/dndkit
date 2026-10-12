"""Concentration (PHB ch. 10): one spell held at a time, a Constitution save
when hurt (DC 10 or half the damage), lost when incapacitated or at 0 hit points."""

from dndkit.game import proficiencies
from dndkit.models import Character, Combatant
from dndkit.text import normalize

INCAPACITATING = frozenset({"incapacitated", "paralyzed", "petrified", "stunned", "unconscious"})

Holder = Character | Combatant


def concentrate(holder: Holder, name: str, spell: str | None) -> str:
    """Hold *spell*, letting go of any other; without one, stop concentrating."""
    before = holder.concentration
    spell = spell.strip() if spell else None
    holder.concentration = spell or None
    if spell:
        same = before is not None and normalize(before) == normalize(spell)
        ended = f" ({before} ends)" if before and not same else ""
        return f"{name} concentrates on {spell}{ended}."
    return f"{name} stops concentrating on {before}." if before else f"{name} held no spell."


def after_damage(holder: Holder, name: str, damage: int, down: bool) -> str | None:
    """The save a hurt creature makes to keep its spell, or the spell lost at 0 HP."""
    if not holder.concentration:
        return None
    if down or INCAPACITATING & set(holder.conditions):
        return lose(holder, name)
    bonus = ""
    if isinstance(holder, Character):
        bonus = f", CON save {proficiencies.save_bonus(holder, 'constitution'):+d}"
    return (
        f"{name} is concentrating on {holder.concentration}: Constitution save DC "
        f"{max(10, damage // 2)}{bonus}. If it fails, set_concentration without a spell."
    )


def lose(holder: Holder, name: str) -> str | None:
    """Let go of the spell held, if any: incapacitated, down, or dead."""
    spell, holder.concentration = holder.concentration, None
    return f"{name} loses concentration on {spell}." if spell else None
