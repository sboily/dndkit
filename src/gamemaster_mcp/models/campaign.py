"""The campaign container, its live game state and its journal.

Older saves keyed characters, NPCs, locations and quests by name and kept a
combat order of free-form dicts; the validators here read those saves as-is.
"""

import re
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, ValidationError, field_validator

from gamemaster_mcp.models.base import GameModel, new_id, now
from gamemaster_mcp.models.battle import Battlefield
from gamemaster_mcp.models.bestiary import Encounter, Monster, Size
from gamemaster_mcp.models.character import Character
from gamemaster_mcp.models.world import NPC, Location, Quest


class Combatant(GameModel):
    """One entry in the initiative order.

    A party character is linked by ``character_id`` and its hit points,
    conditions and speed live on its sheet; any other combatant (monster, NPC)
    keeps its own here, when they are known. ``ally`` puts a non-party
    combatant on the party's side. On a battle map, ``position`` is the
    top-left square it occupies, and the movement fields last one turn.
    """

    name: str = Field(min_length=1)
    initiative: int
    character_id: str | None = None
    monster: str | None = None  # bestiary entry it was built from
    hit_points: int | None = Field(default=None, ge=0)
    hit_points_max: int | None = Field(default=None, ge=1)
    armor_class: int | None = Field(default=None, ge=0)
    xp: int = Field(default=0, ge=0)
    conditions: list[str] = Field(default_factory=list)
    concentration: str | None = None  # the spell held (a character's is on its sheet)
    ally: bool = False
    size: Size = "medium"
    speed: int | None = Field(default=None, ge=0)  # feet; None: 30
    reach: int = Field(default=5, ge=5)
    position: str | None = None
    hidden: bool = False  # unseen by the players: kept off their screens
    boss: bool = False
    legendary_actions: int = Field(default=0, ge=0)  # a round's worth, from the stat block
    legendary_actions_left: int = Field(default=0, ge=0)  # back at the start of its turn
    legendary_resistances_left: int = Field(default=0, ge=0)
    movement_used: int = Field(default=0, ge=0)
    dashed: bool = False
    disengaged: bool = False
    reaction_used: bool = False  # one a round, back at the start of its turn


class Participant(GameModel):
    """Someone joining a fight, as a tool call describes them."""

    name: str = Field(min_length=1, description="Character, monster or NPC name")
    initiative: int = Field(description="Initiative roll")
    hit_points: int | None = Field(default=None, ge=1, description="HP, if not in bestiary")
    armor_class: int | None = Field(default=None, ge=0, description="AC, if not in bestiary")


class Seat(GameModel):
    """A player at the table, as a tool call describes them."""

    player: str = Field(min_length=1, description="Person's name, as their voice is named")
    character: str | None = Field(default=None, description="Character they play")


class CombatRecord(GameModel):
    """What the last fight was, kept once it ends."""

    rounds: int = 0
    fighters: list[str] = Field(default_factory=list)
    defeated: list[str] = Field(default_factory=list)
    xp: int = 0
    ended: datetime = Field(default_factory=now)


class GameState(GameModel):
    """Where the party is and what is happening right now."""

    campaign_name: str
    current_session: int = Field(default=1, ge=1)
    current_date_in_game: str | None = None
    current_location: str | None = None
    party_level: int = Field(default=1, ge=1, le=20)  # legacy: each sheet has its level
    party_funds: str = "0 gp"
    in_combat: bool = False
    initiative_order: list[Combatant] = Field(default_factory=list)
    turn_index: int = Field(default=0, ge=0)
    combat_round: int = Field(default=0, ge=0)
    defeated: list[Combatant] = Field(default_factory=list)  # fallen this combat
    encounter_id: str | None = None  # the planned encounter being fought
    players_present: list[str] = Field(default_factory=list)  # the roll call, in seat order
    battlefield: Battlefield | None = None
    last_combat: CombatRecord | None = None
    notes: str = ""
    updated_at: datetime = Field(default_factory=now)

    @field_validator("initiative_order", mode="before")
    @classmethod
    def _keep_playable_legacy_entries(cls, value: Any) -> Any:
        # Older versions stored any dict the model sent ({"initiative": "15 (Dex)"},
        # no name...): what cannot take a turn must not stop the campaign from loading.
        if not isinstance(value, list):
            return value
        kept: list[Any] = []
        for entry in value:
            if isinstance(entry, dict):
                entry = {**entry, "initiative": _legacy_initiative(entry.get("initiative"))}
                try:
                    Combatant.model_validate(entry)
                except ValidationError:
                    continue
            kept.append(entry)
        return kept

    @property
    def current_combatant(self) -> Combatant | None:
        """Whose turn it is, when a fight is running."""
        if not self.in_combat or not self.initiative_order:
            return None
        return self.initiative_order[self.turn_index % len(self.initiative_order)]


def _legacy_initiative(value: Any) -> int:
    """An old save's initiative as a number: 15, "15 (Dex)", or 0 when missing."""
    if isinstance(value, int | float) and not isinstance(value, bool):
        return int(value)
    match = re.match(r"\s*(-?\d+)", str(value or ""))
    return int(match.group(1)) if match else 0


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
    monsters: dict[str, Monster] = Field(default_factory=dict)
    encounters: dict[str, Encounter] = Field(default_factory=dict)
    sessions: list[SessionNote] = Field(default_factory=list)
    events: list[AdventureEvent] = Field(default_factory=list)
    game_state: GameState
    world_notes: str = ""
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)

    @field_validator(
        "characters", "npcs", "locations", "quests", "monsters", "encounters", mode="after"
    )
    @classmethod
    def _key_by_id(cls, value: dict[str, Any]) -> dict[str, Any]:
        # Entities are keyed by ID: names change and two spellings may collide.
        return {entity.id: entity for entity in value.values()}
