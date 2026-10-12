"""The campaign's bestiary and its planned encounters."""

from typing import Literal

from pydantic import Field

from gamemaster_mcp.models.base import GameModel, new_id
from gamemaster_mcp.models.battle import Battlefield

EncounterStatus = Literal["planned", "running", "done"]
Size = Literal["tiny", "small", "medium", "large", "huge", "gargantuan"]


class Monster(GameModel):
    """A stat block the game master saved, used to fill combatants in."""

    id: str = Field(default_factory=new_id)
    name: str = Field(min_length=1)
    armor_class: int = Field(ge=0)
    hit_points: int = Field(ge=1)
    challenge_rating: str | None = None  # "1/4", "2", ...
    xp: int = Field(default=0, ge=0)
    initiative_bonus: int = 0
    speed: str | None = None  # "30 ft., fly 60 ft."
    size: Size = "medium"
    actions: str = ""  # free text: attacks, damage, special abilities
    notes: str = ""
    boss: bool = False
    legendary_actions: int = Field(default=0, ge=0, le=5)  # a round's worth
    legendary_resistances: int = Field(default=0, ge=0, le=5)  # a day's worth


class EncounterGroup(GameModel):
    """How many of one bestiary monster an encounter holds."""

    monster: str = Field(min_length=1, description="Bestiary monster name")
    count: int = Field(default=1, ge=1, le=50, description="How many")
    at: list[str] = Field(default_factory=list, description="Their squares, if a map")
    hidden: bool = Field(default=False, description="Unseen at first (ambush)")


class Encounter(GameModel):
    """A fight prepared in advance, started with start_combat(encounter=...).

    Older saves stored an unused ``CombatEncounter`` under the same key; its
    extra fields are ignored and its ``description`` still fits.
    """

    id: str = Field(default_factory=new_id)
    name: str = Field(min_length=1)
    description: str = ""
    monsters: list[EncounterGroup] = Field(default_factory=list)
    location: str | None = None
    status: EncounterStatus = "planned"
    notes: str = ""
    battlefield: Battlefield | None = None  # laid out when the fight starts
