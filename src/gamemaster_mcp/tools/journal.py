"""Journal tools: session notes and the adventure log."""

from collections.abc import Callable
from typing import Annotated

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from pydantic import Field

from gamemaster_mcp.game import journal
from gamemaster_mcp.models import AdventureEvent, EventType, SessionNote
from gamemaster_mcp.storage import CampaignStore
from gamemaster_mcp.tools import render
from gamemaster_mcp.tools.deps import READ_ONLY, get_store

Names = Annotated[list[str] | None, Field(description="Character names")]


@tool
def add_session_note(
    session_number: Annotated[int, Field(ge=1, description="Session number")],
    summary: Annotated[str, Field(min_length=1, description="What happened")],
    title: Annotated[str | None, Field(description="Session title")] = None,
    events: Annotated[list[str] | None, Field(description="Key moments")] = None,
    characters_present: Names = None,
    experience_gained: Annotated[int | None, Field(ge=0, description="XP earned")] = None,
    treasure_found: Annotated[list[str] | None, Field(description="Loot")] = None,
    notes: Annotated[str, Field(description="Notes")] = "",
    store: CampaignStore = Depends(get_store),
) -> str:
    """Save the summary of a play session."""
    note = SessionNote(
        session_number=session_number,
        summary=summary,
        title=title,
        events=events or [],
        characters_present=characters_present or [],
        experience_gained=experience_gained,
        treasure_found=treasure_found or [],
        notes=notes,
    )
    with store.transaction() as campaign:
        journal.add_session_note(campaign, note)
    return f"Saved notes for session {session_number}."


@tool(annotations=READ_ONLY)
def get_sessions(store: CampaignStore = Depends(get_store)) -> str:
    """Session notes in play order, summaries shortened."""
    with store.reading() as campaign:
        notes = journal.sessions(campaign)
        if not notes:
            return "No session notes yet."
        return "\n".join(render.session_line(note) for note in notes)


@tool
def add_event(
    event_type: Annotated[EventType, Field(description="Kind of event")],
    title: Annotated[str, Field(min_length=1, description="Short title")],
    description: Annotated[str, Field(description="What happened")],
    session_number: Annotated[
        int | None, Field(ge=1, description="Session; defaults to the current one")
    ] = None,
    characters_involved: Names = None,
    location: Annotated[str | None, Field(description="Where it happened")] = None,
    importance: Annotated[int, Field(ge=1, le=5, description="1 minor to 5 major")] = 3,
    tags: Annotated[list[str] | None, Field(description="Tags for search")] = None,
    store: CampaignStore = Depends(get_store),
) -> str:
    """Log a notable moment in the active campaign's adventure log."""
    event = AdventureEvent(
        event_type=event_type,
        title=title,
        description=description,
        session_number=session_number,
        characters_involved=characters_involved or [],
        location=location,
        importance=importance,
        tags=tags or [],
    )
    with store.transaction() as campaign:
        journal.add_event(campaign, event)
    return f"Logged {event.event_type} event '{event.title}'."


@tool(annotations=READ_ONLY)
def get_events(
    limit: Annotated[int | None, Field(ge=1, description="At most this many")] = 10,
    event_type: Annotated[EventType | None, Field(description="Only this kind")] = None,
    search: Annotated[str | None, Field(description="Text in title, description or tags")] = None,
    store: CampaignStore = Depends(get_store),
) -> str:
    """Recent adventure log entries, newest first; filters combine."""
    with store.reading() as campaign:
        events = journal.find_events(campaign, event_type=event_type, search=search, limit=limit)
        if not events:
            return "No matching events."
        return "\n".join(render.event_line(event) for event in events)


TOOLS: list[Callable[..., str]] = [add_session_note, get_sessions, add_event, get_events]
