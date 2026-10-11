"""Utility tools that need no campaign: dice and rules reminders."""

from collections.abc import Callable
from typing import Annotated

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from pydantic import Field

from gamemaster_mcp.game import dice, reference
from gamemaster_mcp.game.dice import DiceLog
from gamemaster_mcp.tools.apps import DICE_APP, app_meta
from gamemaster_mcp.tools.deps import READ_ONLY, get_dice_log


@tool(meta=app_meta(DICE_APP))
def roll_dice(
    notation: Annotated[
        str, Field(min_length=1, description="Dice to roll, e.g. d20, 1d20+5, 2d6+1d4+3")
    ],
    advantage: Annotated[bool, Field(description="Roll a d20 twice, keep the higher")] = False,
    disadvantage: Annotated[bool, Field(description="Roll a d20 twice, keep the lower")] = False,
    log: DiceLog = Depends(get_dice_log),
) -> str:
    """Roll dice (shown rolling on screen). Advantage and disadvantage cancel out."""
    result = dice.roll(notation, advantage=advantage, disadvantage=disadvantage)
    log.record(result)
    return f"{result.notation}: {result.detail}"


@tool(annotations=READ_ONLY)
def lookup_rule(
    topic: Annotated[str, Field(description="A condition or rule, e.g. prone, cover, à terre")],
) -> str:
    """A short reminder of a 5e rule: conditions, death saves, rests, cover, grapple..."""
    key, text = reference.lookup(topic)
    return f"{key}: {text}"


TOOLS: list[Callable[..., str]] = [roll_dice, lookup_rule]
