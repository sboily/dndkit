"""Errors the game raises when a request cannot be carried out.

They subclass FastMCP's ``ToolError`` on purpose: FastMCP sends a ``ToolError``
message to the client verbatim as an ``is_error`` result, while any other
exception is masked. The model therefore reads "No character named 'Arya'.
Known characters: Aria." and can correct itself, instead of a bare failure.
"""

import logging

from fastmcp.exceptions import ToolError


class GameError(ToolError):
    """A request the game cannot carry out; the message is written for the model."""

    def __init__(self, message: str) -> None:
        # An expected game outcome, not a server fault: keep it out of error logs.
        super().__init__(message, log_level=logging.INFO)


class NotFoundError(GameError):
    """No entity answers to the given name or ID."""


class AlreadyExistsError(GameError):
    """The name is already taken by another entity of the same kind."""


class InvalidChangeError(GameError):
    """The change would leave the game in an invalid state."""


class DiceError(GameError):
    """The dice notation cannot be parsed or is out of bounds."""


NO_ACTIVE_CAMPAIGN = (
    "No campaign is active. Create one with create_campaign "
    "or open one with load_campaign (list_campaigns shows them)."
)


class NoActiveCampaignError(GameError):
    """Every game tool needs an active campaign."""

    def __init__(self, message: str = NO_ACTIVE_CAMPAIGN) -> None:
        super().__init__(message)
