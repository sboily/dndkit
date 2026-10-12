"""The battle map a fight is played on."""

from pydantic import Field

from gamemaster_mcp.models.base import GameModel

MAX_SQUARES = 26  # columns are single letters, A to Z


class Battlefield(GameModel):
    """A grid of 5-foot squares named like "D7": column letter, row number, A1 top left.

    Terrain lists squares by name; who stands where lives on each combatant.
    ``area`` is the last area of effect, drawn until the next turn.
    """

    width: int = Field(ge=1, le=MAX_SQUARES)
    height: int = Field(ge=1, le=MAX_SQUARES)
    walls: list[str] = Field(default_factory=list)  # blocked squares
    difficult: list[str] = Field(default_factory=list)  # each costs 10 feet to enter
    area: list[str] = Field(default_factory=list)
    area_label: str | None = None


class Layout(GameModel):
    """A battle map as a tool call describes it."""

    width: int = Field(ge=1, le=MAX_SQUARES, description="Squares across")
    height: int = Field(ge=1, le=MAX_SQUARES, description="Squares down")
    walls: list[str] = Field(default_factory=list, description='e.g. "C3" or "C1:C6"')
    difficult: list[str] = Field(default_factory=list, description="Difficult terrain")


class Placement(GameModel):
    """A combatant put on a square, or hidden or revealed, as a tool call describes it."""

    who: str = Field(min_length=1, description="Combatant name")
    at: str | None = Field(default=None, description="Square, e.g. D7")
    ally: bool | None = Field(default=None, description="Fights with the party")
    hidden: bool | None = Field(default=None, description="Unseen by the players")
