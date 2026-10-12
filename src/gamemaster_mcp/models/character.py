"""Player characters and what they carry."""

from datetime import datetime
from typing import Any

from pydantic import Field

from gamemaster_mcp.models.base import GameModel, new_id, now

ABILITIES = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")
CONDITIONS = (
    "blinded",
    "charmed",
    "deafened",
    "frightened",
    "grappled",
    "incapacitated",
    "invisible",
    "paralyzed",
    "petrified",
    "poisoned",
    "prone",
    "restrained",
    "stunned",
    "unconscious",
)


class AbilityScore(GameModel):
    """One ability score; the modifier is derived from it."""

    score: int = Field(ge=1, le=30, description="Raw ability score")

    @property
    def mod(self) -> int:
        """The 5e ability modifier."""
        return (self.score - 10) // 2


class CharacterClass(GameModel):
    """Class, level and hit dice."""

    name: str
    level: int = Field(default=1, ge=1, le=20)
    hit_dice: str = "1d8"
    subclass: str | None = None


class Race(GameModel):
    """Race (species) and its traits."""

    name: str
    subrace: str | None = None
    traits: list[str] = Field(default_factory=list)


class Item(GameModel):
    """An inventory entry; identical items stack through ``quantity``."""

    id: str = Field(default_factory=new_id)
    name: str = Field(min_length=1)
    description: str | None = None
    quantity: int = Field(default=1, ge=1)
    weight: float | None = Field(default=None, ge=0)
    value: str | None = None  # e.g. "50 gp"
    item_type: str = "misc"  # weapon, armor, consumable, misc
    properties: dict[str, Any] = Field(default_factory=dict)


class Spell(GameModel):
    """A known spell; only the name and level are required."""

    id: str = Field(default_factory=new_id)
    name: str = Field(min_length=1)
    level: int = Field(ge=0, le=9)  # 0 is a cantrip
    school: str = ""
    casting_time: str = ""
    range: int | str = ""  # free text: "Self", "Touch", "120 feet"
    duration: str = ""
    components: list[str] = Field(default_factory=list)
    description: str = ""
    material_components: str | None = None
    prepared: bool = False


def _default_abilities() -> dict[str, AbilityScore]:
    return {ability: AbilityScore(score=10) for ability in ABILITIES}


class Character(GameModel):
    """A complete character sheet.

    ``hit_points_current`` above ``hit_points_max`` is refused by the game
    logic, not here: a save written by an older version may hold one, and it
    must still load.
    """

    id: str = Field(default_factory=new_id)
    name: str = Field(min_length=1)
    player_name: str | None = None
    character_class: CharacterClass
    race: Race
    background: str | None = None
    alignment: str | None = None
    description: str | None = None  # appearance and demeanor
    bio: str | None = None  # backstory, personality, motivations

    abilities: dict[str, AbilityScore] = Field(default_factory=_default_abilities)

    armor_class: int = Field(default=10, ge=0)
    speed: int = Field(default=30, ge=0)  # walking, in feet
    hit_points_max: int = Field(default=1, ge=1)
    hit_points_current: int = Field(default=1, ge=0)
    temporary_hit_points: int = Field(default=0, ge=0)
    hit_dice_remaining: str = "1d8"
    death_saves_success: int = Field(default=0, ge=0, le=3)
    death_saves_failure: int = Field(default=0, ge=0, le=3)
    conditions: list[str] = Field(default_factory=list)  # names from CONDITIONS
    exhaustion: int = Field(default=0, ge=0, le=6)
    experience_points: int = Field(default=0, ge=0)

    proficiency_bonus: int = 2
    skill_proficiencies: list[str] = Field(default_factory=list)
    saving_throw_proficiencies: list[str] = Field(default_factory=list)

    inventory: list[Item] = Field(default_factory=list)
    equipment: dict[str, Item | None] = Field(default_factory=dict)

    spellcasting_ability: str | None = None
    spell_slots: dict[int, int] = Field(default_factory=dict)  # level -> max slots
    spell_slots_used: dict[int, int] = Field(default_factory=dict)  # level -> used
    spells_known: list[Spell] = Field(default_factory=list)

    features_and_traits: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)

    inspiration: bool = False
    notes: str = ""
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
