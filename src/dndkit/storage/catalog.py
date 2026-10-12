"""What a campaign file holds, read without loading the whole campaign model.

Listing campaigns or describing one before deletion reads the raw JSON: a file
that would fail validation is still listed, marked unreadable.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from dndkit.storage.files import read_json


@dataclass(frozen=True)
class CampaignEntry:
    """A campaign file and a summary of what is in it."""

    name: str
    path: Path
    modified: datetime
    readable: bool = True
    description: str = ""
    characters: int = 0
    npcs: int = 0
    locations: int = 0
    quests: int = 0
    session_notes: int = 0
    events: int = 0
    current_session: int = 1


def read_entry(path: Path) -> CampaignEntry:
    """The summary of one campaign file; never raises for a bad file."""
    modified = datetime.fromtimestamp(modified_at(path))
    try:
        data = read_json(path)
    except (OSError, ValueError, RecursionError):
        data = None
    if not isinstance(data, dict):
        return CampaignEntry(
            name=f"{path.stem} (unreadable)", path=path, modified=modified, readable=False
        )
    name = data.get("name")
    state = data.get("game_state")
    session = state.get("current_session") if isinstance(state, dict) else None
    return CampaignEntry(
        name=name if isinstance(name, str) and name else path.stem,
        path=path,
        modified=modified,
        description=str(data.get("description") or ""),
        characters=_count(data, "characters"),
        npcs=_count(data, "npcs"),
        locations=_count(data, "locations"),
        quests=_count(data, "quests"),
        session_notes=_count(data, "sessions"),
        events=_count(data, "events"),
        current_session=session if isinstance(session, int) else 1,
    )


def _count(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    return len(value) if isinstance(value, dict | list) else 0


def modified_at(path: Path) -> float:
    """When *path* last changed; 0 for a file gone or a dangling link."""
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0
