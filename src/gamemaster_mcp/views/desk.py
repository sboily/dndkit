"""The game master's desk, to follow and debug the model: what it called,
the campaign's notebook, the full sheets, and the server's own facts."""

import time
from pathlib import Path

from gamemaster_mcp import __version__
from gamemaster_mcp.activity import ActivityLog
from gamemaster_mcp.models import Campaign
from gamemaster_mcp.skills import load_catalog
from gamemaster_mcp.views import everyone
from gamemaster_mcp.views.everyone import Json

SHOWN_CALLS = 60
SHOWN_SESSIONS = 6


def activity(log: ActivityLog) -> Json:
    """The model's latest calls, newest first."""
    calls = log.recent()[-SHOWN_CALLS:]
    return {
        "calls": [
            {
                "n": c.number,
                "time": time.strftime("%H:%M:%S", time.localtime(c.at)),
                "kind": c.kind,
                "name": c.name,
                "arguments": c.arguments,
                "outcome": c.outcome,
                "failed": c.failed,
                "ms": c.milliseconds,
            }
            for c in reversed(calls)
        ],
        "failures": sum(c.failed for c in calls),
    }


def notebook(campaign: Campaign, saved_in: Path | None, data_dir: Path) -> Json:
    """The campaign as the model's tools hold it, beyond the board: notes, the
    setting, past sessions, and where it all lives."""
    state = campaign.game_state
    return {
        "situation": state.notes,
        "world_notes": campaign.world_notes,
        "setting": campaign.setting,
        "dm": campaign.dm_name,
        "sessions": [
            {
                "number": s.session_number,
                "title": s.title,
                "summary": s.summary,
                "moments": s.events,
                "present": s.characters_present,
                "xp": s.experience_gained,
                "treasure": s.treasure_found,
                "notes": s.notes,
            }
            for s in sorted(campaign.sessions, key=lambda s: s.session_number)[-SHOWN_SESSIONS:]
        ],
        "server": {
            "version": __version__,
            "data_dir": str(data_dir),
            "file": saved_in.name if saved_in else None,
            "saved": campaign.updated_at.astimezone().strftime("%Y-%m-%d %H:%M:%S"),
            "skills": [s.name for s in load_catalog()],
        },
    }


def sheets(campaign: Campaign) -> Json:
    """Every character's full sheet, with the game master's notes on it."""
    party = sorted(campaign.characters.values(), key=lambda c: c.name)
    return {
        "sheets": [{**everyone.character(campaign, c.id), "notes": c.notes} for c in party],
    }
