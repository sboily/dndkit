"""The campaign container, its live game state and its journal.

Older saves keyed characters, NPCs, locations and quests by name and kept a
combat order of free-form dicts; the validators here read those saves as-is.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator

from gamemaster_mcp.models.base import GameModel, new_id, now
from gamemaster_mcp.models.character import Character
from gamemaster_mcp.models.world import NPC, Location, Quest


class Combatant(GameModel):
    """One entry in the initiative order."""

    name: str = Field(min_length=1, description="Combatant name, e.g. 'Aria' or 'Goblin'")
    initiative: int = Field(description="Initiative roll result")


class GameState(GameModel):
    """Where the party is and what is happening right now."""

    campaign_name: str
    current_session: int = Field(default=1, ge=1)
    current_date_in_game: str | None = None
    current_location: str | None = None
    party_level: int = Field(default=1, ge=1, le=20)
    party_funds: str = "0 gp"
    in_combat: bool = False
    initiative_order: list[Combatant] = Field(default_factory=list)
    turn_index: int = Field(default=0, ge=0)
    combat_round: int = Field(default=0, ge=0)
    notes: str = ""
    updated_at: datetime = Field(default_factory=now)

    @field_validator("initiative_order", mode="before")
    @classmethod
    def _drop_unnamed_legacy_entries(cls, value: Any) -> Any:
        # Older versions stored any dict the model sent; one without a name
        # cannot take a turn, and must not stop the campaign from loading.
        if isinstance(value, list):
            return [entry for entry in value if not isinstance(entry, dict) or entry.get("name")]
        return value

    @property
    def current_combatant(self) -> Combatant | None:
        """Whose turn it is, when a fight is running."""
        if not self.in_combat or not self.initiative_order:
            return None
        return self.initiative_order[self.turn_index % len(self.initiative_order)]


class SessionNote(GameModel):
    """A summary of one play session."""

    id: str = Field(default_factory=new_id)
    session_number: int = Field(ge=1)
    date: datetime = Field(default_factory=now)
    title: str | None = None
    summary: str
    events: list[str] = Field(default_factory=list)
    characters_present: list[str] = Field(default_factory=list)
    experience_gained: int | None = Field(default=None, ge=0)
    treasure_found: list[str] = Field(default_factory=list)
    notes: str = ""


class EventType(StrEnum):
    """Categories of the adventure log."""

    COMBAT = "combat"
    ROLEPLAY = "roleplay"
    EXPLORATION = "exploration"
    QUEST = "quest"
    CHARACTER = "character"
    WORLD = "world"
    SESSION = "session"


class AdventureEvent(GameModel):
    """One entry of the campaign's adventure log."""

    id: str = Field(default_factory=new_id)
    event_type: EventType
    title: str
    description: str
    timestamp: datetime = Field(default_factory=now)
    session_number: int | None = None
    characters_involved: list[str] = Field(default_factory=list)
    location: str | None = None
    tags: list[str] = Field(default_factory=list)
    importance: int = Field(default=3, ge=1, le=5)  # 1 minor .. 5 major


class Campaign(GameModel):
    """Everything one campaign holds; saved as one JSON file."""

    id: str = Field(default_factory=new_id)
    name: str = Field(min_length=1)
    description: str
    dm_name: str | None = None
    setting: str | None = None
    characters: dict[str, Character] = Field(default_factory=dict)
    npcs: dict[str, NPC] = Field(default_factory=dict)
    locations: dict[str, Location] = Field(default_factory=dict)
    quests: dict[str, Quest] = Field(default_factory=dict)
    sessions: list[SessionNote] = Field(default_factory=list)
    events: list[AdventureEvent] = Field(default_factory=list)
    game_state: GameState
    world_notes: str = ""
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)

    @field_validator("characters", "npcs", "locations", "quests", mode="after")
    @classmethod
    def _key_by_id(cls, value: dict[str, Any]) -> dict[str, Any]:
        # Entities are keyed by ID: names change and two spellings may collide.
        return {entity.id: entity for entity in value.values()}
