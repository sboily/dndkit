"""Plain-text views of fights, monsters and encounters."""

from gamemaster_mcp.game import bestiary, rules
from gamemaster_mcp.models import Campaign, Combatant, Encounter, Monster


def combatant_line(campaign: Campaign, combatant: Combatant) -> str:
    """Initiative, hit points, AC and conditions, from the sheet for a character."""
    character = campaign.characters.get(combatant.character_id or "")
    parts = [f"initiative {combatant.initiative}"]
    if character is not None:
        parts.append(f"HP {character.hit_points_current}/{character.hit_points_max}")
        parts.append(f"AC {character.armor_class}")
        conditions = character.conditions
    else:
        if combatant.hit_points is not None:
            parts.append(f"HP {combatant.hit_points}/{combatant.hit_points_max}")
        if combatant.armor_class is not None:
            parts.append(f"AC {combatant.armor_class}")
        conditions = combatant.conditions
    if conditions:
        parts.append(", ".join(conditions))
    return "; ".join(parts)


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
    lines = [
        f"{m.name}: AC {m.armor_class}, HP {m.hit_points}{challenge}, {m.xp} XP, "
        f"initiative {m.initiative_bonus:+d}{f', speed {m.speed}' if m.speed else ''}."
    ]
    lines += [
        f"{label}: {value}"
        for label, value in (("Actions", m.actions), ("Notes", m.notes))
        if value
    ]
    return "\n".join(lines)


def encounter(campaign: Campaign, e: Encounter) -> str:
    """An encounter with its monsters and its difficulty for the current party."""
    groups = ", ".join(f"{g.count} {g.monster}" for g in e.monsters) or "no monster"
    where = f" at {e.location}" if e.location else ""
    line = f"{e.name} [{e.status}]{where}: {groups}."
    rated = bestiary.difficulty(campaign, e)
    if rated is not None:
        line += f" {difficulty(rated)}"
    if e.description:
        line += f" {e.description}"
    return line


def difficulty(rated: rules.Difficulty) -> str:
    """A difficulty rating with its numbers."""
    easy, medium, hard, deadly = rated.thresholds
    return (
        f"Difficulty {rated.rating}: {rated.total_xp} XP, adjusted {rated.adjusted_xp} "
        f"(x{rated.multiplier:g}); party thresholds easy {easy}, medium {medium}, "
        f"hard {hard}, deadly {deadly}."
    )
