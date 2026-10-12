"""Plain-text views of fights, monsters and encounters."""

from dndkit.game import bestiary, effects, rules
from dndkit.models import (
    Campaign,
    Character,
    Combatant,
    Encounter,
    EncounterGroup,
    Monster,
)


def combatant_line(campaign: Campaign, combatant: Combatant) -> str:
    """Initiative, hit points, AC and conditions, from the sheet for a character."""
    character = campaign.characters.get(combatant.character_id or "")
    parts = [f"initiative {combatant.initiative}"]
    if character is not None:
        parts.append(f"HP {character.hit_points_current}/{character.hp_maximum}")
        parts.append(f"AC {character.armor_class}")
        holder: Character | Combatant = character
    else:
        if combatant.hit_points is not None:
            parts.append(f"HP {combatant.hit_points}/{combatant.hit_points_max}")
        if combatant.armor_class is not None:
            parts.append(f"AC {combatant.armor_class}")
        holder = combatant
    if holder.conditions:
        parts.append(effects.timed(holder))
    held = character.concentration if character is not None else combatant.concentration
    if held:
        parts.append(f"concentrating on {held}")
    if combatant.position:
        parts.append(f"at {combatant.position}")
    if combatant.reaction_used:
        parts.append("reaction used")
    if combatant.hidden:
        parts.append("hidden from the players")
    if combatant.boss:
        parts.append("boss")
    if combatant.legendary_actions or combatant.legendary_resistances_left:
        parts.append(
            f"legendary actions {combatant.legendary_actions_left}/"
            f"{combatant.legendary_actions}, resistances {combatant.legendary_resistances_left}"
        )
    return "; ".join(parts)


def turn_hint(campaign: Campaign, combatant: Combatant) -> str | None:
    """What a character down at 0 HP does on their turn."""
    character = campaign.characters.get(combatant.character_id or "")
    if character is None or character.hit_points_current > 0:
        return None
    if character.death_saves_failure >= 3:
        return f"{character.name} is dead: call next_turn."
    if character.stable:
        return f"{character.name} is stable at 0 HP: call next_turn."
    return f"{character.name} is down: roll a death save (d20) and call record_death_save."


def initiative(campaign: Campaign) -> str:
    """The initiative order, the current combatant marked."""
    state = campaign.game_state
    current = state.current_combatant
    rows = [
        f"{n}. {c.name} ({combatant_line(campaign, c)}){' <- now' if c is current else ''}"
        for n, c in enumerate(state.initiative_order, 1)
    ]
    return f"Round {state.combat_round}.\n" + "\n".join(rows)


def monster(m: Monster) -> str:
    """A saved stat block."""
    challenge = f", CR {m.challenge_rating}" if m.challenge_rating else ""
    speed = f", speed {m.speed.rstrip('. ')}" if m.speed else ""
    size = f", {m.size}" if m.size != "medium" else ""
    lines = [
        f"{m.name}{' (boss)' if m.boss else ''}: AC {m.armor_class}, HP {m.hit_points}"
        f"{challenge}, {m.xp} XP, initiative {m.initiative_bonus:+d}{speed}{size}."
    ]
    if m.legendary_actions or m.legendary_resistances:
        lines.append(
            f"Legendary: {m.legendary_actions} actions a round, "
            f"{m.legendary_resistances} resistances a day."
        )
    lines += [
        f"{label}: {value}"
        for label, value in (("Actions", m.actions), ("Notes", m.notes))
        if value
    ]
    return "\n".join(lines)


def encounter(campaign: Campaign, e: Encounter) -> str:
    """An encounter with its monsters and its difficulty for the current party."""
    groups = ", ".join(_group(g) for g in e.monsters) or "no monster"
    where = f" at {e.location}" if e.location else ""
    line = f"{e.name} [{e.status}]{where}: {groups}."
    if e.battlefield is not None:
        line += f" On a {e.battlefield.width}x{e.battlefield.height} battle map."
    rated = bestiary.difficulty(campaign, e)
    if rated is not None:
        line += f" {difficulty(rated)}"
    if e.description:
        line += f" {e.description}"
    return line


def _group(g: EncounterGroup) -> str:
    details = [*(["hidden"] if g.hidden else []), *([f"at {', '.join(g.at)}"] if g.at else [])]
    return f"{g.count} {g.monster}" + (f" ({'; '.join(details)})" if details else "")


def difficulty(rated: rules.Difficulty) -> str:
    """A difficulty rating with its numbers."""
    easy, medium, hard, deadly = rated.thresholds
    return (
        f"Difficulty {rated.rating}: {rated.total_xp} XP, adjusted {rated.adjusted_xp} "
        f"(x{rated.multiplier:g}); party thresholds easy {easy}, medium {medium}, "
        f"hard {hard}, deadly {deadly}."
    )
