"""Plain-text views of game data, written for a model that will speak them.

No emoji and little markup: a voice model reads these, then says what
matters in its own words.
"""

from gamemaster_mcp.game import seating
from gamemaster_mcp.game.spellbook import describe_slots
from gamemaster_mcp.models import (
    ABILITIES,
    NPC,
    AdventureEvent,
    Campaign,
    Character,
    Location,
    Quest,
    SessionNote,
)
from gamemaster_mcp.storage import CampaignEntry
from gamemaster_mcp.tools import render_combat


def character_line(c: Character) -> str:
    """One-line summary: name, ID, class and hit points."""
    cls = c.character_class
    return (
        f"{c.name} (id {c.id}): level {cls.level} {c.race.name} {cls.name}, "
        f"HP {c.hit_points_current}/{c.hit_points_max}, AC {c.armor_class}"
    )


def character_sheet(c: Character) -> str:
    """The full sheet, one fact per line, empty sections left out."""
    scores = ", ".join(
        f"{name[:3].upper()} {c.abilities[name].score} ({c.abilities[name].mod:+d})"
        for name in ABILITIES
        if name in c.abilities
    )
    lines = [
        character_line(c),
        f"Player: {c.player_name or 'unknown'}. Background: {c.background or 'none'}. "
        f"Alignment: {c.alignment or 'none'}.",
        f"Abilities: {scores}.",
        f"Temporary HP {c.temporary_hit_points}. Proficiency +{c.proficiency_bonus}. "
        f"Inspiration: {'yes' if c.inspiration else 'no'}. XP {c.experience_points}.",
    ]
    if c.conditions or c.exhaustion:
        exhaustion = [f"exhaustion {c.exhaustion}"] if c.exhaustion else []
        lines.append(f"Conditions: {', '.join([*c.conditions, *exhaustion])}.")
    if c.hit_points_current == 0:
        lines.append(
            f"Death saves: {c.death_saves_success} successes, {c.death_saves_failure} failures."
        )
    optional = {
        "Description": c.description,
        "Bio": c.bio,
        "Inventory": ", ".join(f"{i.name} x{i.quantity}" for i in c.inventory),
        "Spell slots": describe_slots(c) if c.spell_slots else "",
        "Spells": ", ".join(
            f"{s.name} ({'cantrip' if s.level == 0 else f'level {s.level}'}"
            f"{', prepared' if s.prepared else ''})"
            for s in sorted(c.spells_known, key=lambda s: (s.level, s.name))
        ),
        "Skills": ", ".join(c.skill_proficiencies),
        "Saving throws": ", ".join(c.saving_throw_proficiencies),
        "Features": ", ".join(c.features_and_traits),
        "Languages": ", ".join(c.languages),
        "Notes": c.notes,
    }
    lines += [f"{label}: {value}" for label, value in optional.items() if value]
    return "\n".join(lines)


def npc(n: NPC) -> str:
    """An NPC, private bio included: the game master's eyes only."""
    lines = [
        f"{n.name} (id {n.id}): {n.race or 'unknown race'}, {n.occupation or 'no occupation'}, "
        f"at {n.location or 'unknown location'}, attitude {n.attitude or 'unknown'}."
    ]
    lines += [
        f"{label}: {value}"
        for label, value in (("Description", n.description), ("Bio", n.bio), ("Notes", n.notes))
        if value
    ]
    if n.relationships:
        lines.append(
            "Relationships: " + ", ".join(f"{k}: {v}" for k, v in n.relationships.items())
        )
    return "\n".join(lines)


def location(loc: Location) -> str:
    """A location and what is known about it."""
    lines = [f"{loc.name} (id {loc.id}), {loc.location_type}: {loc.description}"]
    if loc.population is not None:
        lines.append(f"Population: {loc.population}.")
    optional = {
        "Government": loc.government,
        "Notable features": "; ".join(loc.notable_features),
        "NPCs": ", ".join(loc.npcs),
        "Connections": ", ".join(loc.connections),
        "Notes": loc.notes,
    }
    lines += [f"{label}: {value}" for label, value in optional.items() if value]
    return "\n".join(lines)


def quest(q: Quest) -> str:
    """A quest with its objectives numbered and marked done or open."""
    lines = [f"{q.title} (id {q.id}), {q.status}: {q.description}"]
    if q.giver:
        lines.append(f"Given by {q.giver}.")
    for number, objective in enumerate(q.objectives, 1):
        mark = "done" if objective in q.completed_objectives else "open"
        lines.append(f"{number}. [{mark}] {objective}")
    lines += [
        f"{label}: {value}" for label, value in (("Reward", q.reward), ("Notes", q.notes)) if value
    ]
    return "\n".join(lines)


def game_state(campaign: Campaign) -> str:
    """Where the party stands right now."""
    state = campaign.game_state
    active = [q.title for q in campaign.quests.values() if q.status == "active"]
    party = sorted(campaign.characters.values(), key=lambda c: c.name)
    lines = [
        f"Campaign {campaign.name}, session {state.current_session}.",
        f"Location: {state.current_location or 'unknown'}. "
        f"In-game date: {state.current_date_in_game or 'unknown'}.",
        f"Party level {state.party_level}, funds {state.party_funds}.",
        "Party: "
        + (
            ", ".join(f"{c.name} HP {c.hit_points_current}/{c.hit_points_max}" for c in party)
            or "none"
        ),
        f"Active quests: {', '.join(active) or 'none'}.",
        table(campaign),
    ]
    if state.in_combat:
        lines.append("In combat. " + render_combat.initiative(campaign))
    if state.notes:
        lines.append(f"Notes: {state.notes}")
    return "\n".join(lines)


def table(campaign: Campaign) -> str:
    """Who plays which character tonight, so the model knows whom it speaks to."""
    party = sorted(campaign.characters.values(), key=lambda c: c.name)
    present = campaign.game_state.players_present
    if not present:
        known = [f"{c.player_name} plays {c.name}" for c in party if c.player_name]
        return "Nobody seated yet: ask who is playing, then seat_players." + (
            f" Known players: {', '.join(known)}." if known else ""
        )
    seats = []
    for player in present:
        played = " and ".join(c.name for c in seating.characters_of(campaign, player))
        seats.append(f"{player} plays {played}" if played else f"{player} has no character yet")
    lines = [f"At the table: {'; '.join(seats)}."]
    away = [
        f"{c.name} ({c.player_name})"
        for c in party
        if c.player_name and not seating.is_present(campaign, c)
    ]
    if away:
        lines.append(f"Absent: {', '.join(away)}.")
    unplayed = [c.name for c in party if not c.player_name]
    if unplayed:
        lines.append(f"Nobody plays {', '.join(unplayed)}.")
    return " ".join(lines)


def campaign_contents(entry: CampaignEntry) -> str:
    """What a campaign holds, e.g. "3 characters, 5 NPCs, ... and 12 log events"."""
    return (
        f"{entry.characters} characters, {entry.npcs} NPCs, {entry.locations} locations, "
        f"{entry.quests} quests, {entry.session_notes} session notes "
        f"and {entry.events} log events"
    )


def campaign_entry(entry: CampaignEntry, active: bool) -> str:
    """One saved campaign: pitch, size, session and when it was last used."""
    marker = " (active)" if active else ""
    if not entry.readable:
        return f"{entry.name}{marker}: the file cannot be read."
    pitch = f" {_short(entry.description, 100)}." if entry.description else ""
    return (
        f"{entry.name}{marker}:{pitch} {entry.characters} characters, "
        f"{entry.quests} quests, at session {entry.current_session}, "
        f"last used {entry.modified:%Y-%m-%d %H:%M}."
    )


def session_line(note: SessionNote) -> str:
    """One session note, summary shortened."""
    title = f" '{note.title}'" if note.title else ""
    return f"Session {note.session_number}{title} ({note.date:%Y-%m-%d}): {_short(note.summary)}"


def event_line(event: AdventureEvent) -> str:
    """One adventure log entry."""
    where = f" at {event.location}" if event.location else ""
    session = f", session {event.session_number}" if event.session_number else ""
    return (
        f"[{event.event_type}, importance {event.importance}{session}] "
        f"{event.title}{where}: {_short(event.description, 200)}"
    )


def _short(text: str, limit: int = 150) -> str:
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."
