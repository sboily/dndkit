"""Session notes and the campaign's adventure log."""

from dndkit.models import AdventureEvent, Campaign, EventType, SessionNote
from dndkit.text import normalize


def add_session_note(campaign: Campaign, note: SessionNote) -> SessionNote:
    """Record a session summary."""
    campaign.sessions.append(note)
    return note


def sessions(campaign: Campaign) -> list[SessionNote]:
    """Session notes in play order."""
    return sorted(campaign.sessions, key=lambda note: (note.session_number, note.date))


def add_event(campaign: Campaign, event: AdventureEvent) -> AdventureEvent:
    """Log an event; it belongs to the current session unless it says otherwise."""
    if event.session_number is None:
        event.session_number = campaign.game_state.current_session
    campaign.events.append(event)
    return event


def find_events(
    campaign: Campaign,
    *,
    event_type: EventType | None = None,
    search: str | None = None,
    limit: int | None = None,
) -> list[AdventureEvent]:
    """Events newest first, filtered by type and by text in title, description or tags."""
    events = campaign.events
    if event_type is not None:
        events = [e for e in events if e.event_type == event_type]
    if search:
        needle = normalize(search)
        events = [
            e
            for e in events
            if needle in normalize(e.title)
            or needle in normalize(e.description)
            or any(needle in normalize(tag) for tag in e.tags)
        ]
    events = sorted(events, key=lambda e: e.timestamp, reverse=True)
    return events[:limit] if limit else events
