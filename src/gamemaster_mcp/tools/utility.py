"""Utility tools that need no campaign: dice and experience."""

from collections.abc import Callable
from typing import Annotated

from fastmcp.tools import tool
from pydantic import Field

from gamemaster_mcp.game import dice, rules


@tool
def roll_dice(
    notation: Annotated[
        str, Field(min_length=1, description="Dice to roll, e.g. d20, 1d20+5, 2d6+1d4+3")
    ],
    advantage: Annotated[bool, Field(description="Roll a d20 twice, keep the higher")] = False,
    disadvantage: Annotated[bool, Field(description="Roll a d20 twice, keep the lower")] = False,
) -> str:
    """Roll dice. Advantage and disadvantage apply to a single d20 and cancel each other."""
    result = dice.roll(notation, advantage=advantage, disadvantage=disadvantage)
    return f"{result.notation}: {result.detail}"


@tool
def calculate_experience(
    party_size: Annotated[int, Field(ge=1, description="Characters sharing the XP")],
    encounter_xp: Annotated[int, Field(ge=0, description="Total XP of the defeated monsters")],
) -> str:
    """XP each character earns: the monsters' total split evenly (5e DMG)."""
    share = rules.experience_per_character(encounter_xp, party_size)
    return f"{encounter_xp} XP split between {party_size}: {share} XP each."


TOOLS: list[Callable[..., str]] = [roll_dice, calculate_experience]
