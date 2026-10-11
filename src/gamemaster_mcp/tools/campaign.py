"""Campaign tools: create, open, list, describe, edit and delete campaigns."""

from collections.abc import Callable
from typing import Annotated

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from pydantic import Field

from gamemaster_mcp.errors import InvalidChangeError
from gamemaster_mcp.game import world
from gamemaster_mcp.game.world import EntityKind
from gamemaster_mcp.storage import CampaignStore
from gamemaster_mcp.tools import render
from gamemaster_mcp.tools.deps import DESTRUCTIVE, READ_ONLY, NameOrId, get_store, provided

Setting = Annotated[str | None, Field(description="World and tone, in prose or markdown")]
SettingFile = Annotated[
    str | None,
    Field(description="Name of a .md or .txt file in the server's settings folder"),
]


def _setting_text(
    store: CampaignStore, setting: str | None, setting_file: str | None
) -> str | None:
    if setting and setting_file:
        raise InvalidChangeError("Give either setting or setting_file, not both.")
    return store.read_setting_file(setting_file) if setting_file else setting


@tool
def create_campaign(
    name: Annotated[str, Field(min_length=1, description="Campaign name")],
    description: Annotated[str, Field(description="One-line pitch of the campaign")],
    dm_name: Annotated[str | None, Field(description="Game master's name")] = None,
    setting: Setting = None,
    setting_file: SettingFile = None,
    store: CampaignStore = Depends(get_store),
) -> str:
    """Create a campaign and make it active. An existing campaign is never replaced."""
    text = _setting_text(store, setting, setting_file)
    campaign = store.create(name, description, dm_name=dm_name, setting=text)
    return f"Campaign '{campaign.name}' created and active."


@tool(annotations=READ_ONLY)
def get_campaign_info(store: CampaignStore = Depends(get_store)) -> str:
    """Describe the active campaign: pitch, setting, sizes and world notes."""
    with store.reading() as c:
        lines = [
            f"{c.name} (id {c.id}): {c.description}",
            f"Game master: {c.dm_name or 'unknown'}.",
            f"{len(c.characters)} characters, {len(c.npcs)} NPCs, {len(c.locations)} locations, "
            f"{len(c.quests)} quests, {len(c.sessions)} session notes, "
            f"{len(c.events)} log events.",
            f"Setting: {c.setting or 'not described yet'}",
        ]
        if c.world_notes:
            lines.append(f"World notes: {c.world_notes}")
    return "\n".join(lines)


@tool(annotations=READ_ONLY)
def list_campaigns(store: CampaignStore = Depends(get_store)) -> str:
    """List saved campaigns, most recently used first, with their size and session."""
    entries = store.list_campaigns()
    if not entries:
        return f"No campaign saved yet in {store.campaigns_dir}."
    active = store.current.name if store.current else None
    return "Campaigns:\n" + "\n".join(
        f"- {render.campaign_entry(e, e.name == active)}" for e in entries
    )


@tool
def load_campaign(
    name: Annotated[str, Field(min_length=1, description="Campaign name")],
    store: CampaignStore = Depends(get_store),
) -> str:
    """Open a saved campaign and make it active."""
    campaign = store.load(name)
    return f"Campaign '{campaign.name}' is active."


@tool
def update_campaign(
    description: Annotated[str | None, Field(description="New pitch")] = None,
    dm_name: Annotated[str | None, Field(description="Game master's name")] = None,
    setting: Setting = None,
    setting_file: SettingFile = None,
    world_notes: Annotated[str | None, Field(description="Replaces the world notes")] = None,
    store: CampaignStore = Depends(get_store),
) -> str:
    """Edit the active campaign's pitch, game master, setting or world notes."""
    changes = provided(
        description=description,
        dm_name=dm_name,
        setting=_setting_text(store, setting, setting_file),
        world_notes=world_notes,
    )
    if not changes:
        raise InvalidChangeError("Nothing to change: give at least one field.")
    with store.transaction() as campaign:
        for field, value in changes.items():
            setattr(campaign, field, value)
    return f"Campaign '{campaign.name}' updated: {', '.join(changes)}."


@tool(annotations=DESTRUCTIVE)
def remove_from_campaign(
    kind: Annotated[EntityKind, Field(description="What to remove")],
    name_or_id: NameOrId,
    store: CampaignStore = Depends(get_store),
) -> str:
    """Permanently remove a character, NPC, location or quest. Confirm with the user first."""
    with store.transaction() as campaign:
        name = world.remove_entity(campaign, kind, name_or_id)
    return f"Removed {kind} '{name}'."


@tool(annotations=DESTRUCTIVE)
def delete_campaign(
    name: Annotated[str, Field(min_length=1, description="Campaign name")],
    confirmation_code: Annotated[
        str | None,
        Field(description="Code from the first call, once the user has said yes"),
    ] = None,
    store: CampaignStore = Depends(get_store),
) -> str:
    """Delete a campaign in two calls. The first only returns a code and what would be lost:
    ask the user out loud, and call again with the code only after a clear yes."""
    if confirmation_code is None:
        entry, code = store.request_deletion(name)
        return (
            f"Nothing deleted yet. Campaign '{entry.name}' holds "
            f"{render.campaign_contents(entry)}. Ask the user to confirm the deletion. "
            f"Only if they clearly say yes, call delete_campaign again with "
            f"confirmation_code '{code}' (valid {store.confirmations.ttl_minutes} minutes)."
        )
    entry, moved_to = store.delete(name, confirmation_code)
    active = store.current.name if store.current else None
    after = f" '{active}' is still active." if active else " No campaign is active now."
    return f"Campaign '{entry.name}' deleted (file moved to {moved_to}).{after}"


TOOLS: list[Callable[..., str]] = [
    create_campaign,
    get_campaign_info,
    list_campaigns,
    load_campaign,
    update_campaign,
    delete_campaign,
    remove_from_campaign,
]
