"""What tools share: the campaign store dependency and common parameter types."""

from typing import Annotated, Any

from fastmcp import Context
from fastmcp.dependencies import CurrentContext
from pydantic import Field

from gamemaster_mcp.storage import CampaignStore

STORE_KEY = "store"

READ_ONLY: dict[str, Any] = {"readOnlyHint": True}
DESTRUCTIVE: dict[str, Any] = {"destructiveHint": True}

NameOrId = Annotated[str, Field(min_length=1, description="Name or ID")]


def get_store(ctx: Context = CurrentContext()) -> CampaignStore:
    """The store opened by the server's lifespan (see ``app.build_server``)."""
    store = ctx.lifespan_context.get(STORE_KEY)
    if not isinstance(store, CampaignStore):
        raise RuntimeError("The campaign store is not open: the server lifespan did not run.")
    return store


def provided(**fields: Any) -> dict[str, Any]:
    """The fields the model actually sent: None means "leave unchanged"."""
    return {name: value for name, value in fields.items() if value is not None}
