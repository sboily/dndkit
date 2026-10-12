"""The world around the party: NPCs, places and quests."""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from dndkit.models.base import GameModel, new_id, now

Attitude = Literal["friendly", "neutral", "hostile", "unknown"]
QuestStatus = Literal["active", "completed", "failed", "on_hold"]


class NPC(GameModel):
    """A non-player character."""

    id: str = Field(default_factory=new_id)
    name: str = Field(min_length=1)
    description: str | None = None  # public
    bio: str | None = None  # private: backstory, motivations, secrets
    race: str | None = None
    occupation: str | None = None
    location: str | None = None
    attitude: Attitude | None = None
    notes: str = ""
    stats: dict[str, Any] | None = None
    relationships: dict[str, str] = Field(default_factory=dict)  # who -> relationship


class Location(GameModel):
    """A place: settlement, dungeon, region."""

    id: str = Field(default_factory=new_id)
    name: str = Field(min_length=1)
    location_type: str  # city, town, village, dungeon, forest...
    description: str
    population: int | None = Field(default=None, ge=0)
    government: str | None = None
    notable_features: list[str] = Field(default_factory=list)
    npcs: list[str] = Field(default_factory=list)
    connections: list[str] = Field(default_factory=list)
    notes: str = ""


class Quest(GameModel):
    """A quest and its objectives."""

    id: str = Field(default_factory=new_id)
    title: str = Field(min_length=1)
    description: str
    giver: str | None = None
    status: QuestStatus = "active"
    objectives: list[str] = Field(default_factory=list)
    completed_objectives: list[str] = Field(default_factory=list)
    reward: str | None = None
    notes: str = ""
    created_at: datetime = Field(default_factory=now)

    @property
    def name(self) -> str:
        """The title, so quests are looked up like every other entity."""
        return self.title
