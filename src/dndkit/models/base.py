"""Shared base for the game's data models."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict
from shortuuid import random as short_random


def new_id() -> str:
    """A random 8-character ID."""
    return short_random(length=8)


def now() -> datetime:
    """The current local time, for created/updated stamps."""
    return datetime.now()


class GameModel(BaseModel):
    """Assignments are validated; keys left by older versions are ignored on load.

    No validator may assign to ``self``: with ``validate_assignment`` that
    assignment would validate again and recurse.
    """

    model_config = ConfigDict(validate_assignment=True, extra="ignore")
