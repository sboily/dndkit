"""Deleting a campaign takes a confirmed second call and keeps the file in the trash."""

import re
from pathlib import Path

import pytest
from fastmcp import Client

from gamemaster_mcp.errors import InvalidChangeError, NotFoundError
from gamemaster_mcp.storage import CampaignStore
from gamemaster_mcp.storage.confirmations import Confirmations
from tests.helpers import call, call_error


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_a_code_serves_once_for_its_target_only() -> None:
    confirmations = Confirmations()
    code = confirmations.issue("a")
    assert not confirmations.consume("b", code)
    assert confirmations.consume("a", code)
    assert not confirmations.consume("a", code)


def test_a_wrong_code_cancels_the_request() -> None:
    confirmations = Confirmations()
    code = confirmations.issue("a")
    assert not confirmations.consume("a", "wrong")
    assert not confirmations.consume("a", code)


def test_codes_expire() -> None:
    clock = FakeClock()
    confirmations = Confirmations(ttl=300, clock=clock)
    code = confirmations.issue("a")
    clock.now = 301
    assert not confirmations.consume("a", code)


def test_delete_moves_the_file_to_the_trash(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path)
    store.create("Ghost Coast", "d")
    store.create("Second", "d")
    entry, code = store.request_deletion("ghost coast")
    assert entry.name == "Ghost Coast"
    _, moved_to = store.delete("Ghost Coast", code)
    assert moved_to.parent == store.trash_dir and moved_to.exists()
    assert [e.name for e in store.list_campaigns()] == ["Second"]
    assert store.current is not None and store.current.name == "Second"


def test_deleting_the_active_campaign_leaves_none_active(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path)
    store.create("Ghost Coast", "d")
    _, code = store.request_deletion("Ghost Coast")
    store.delete("Ghost Coast", code)
    assert store.current is None


def test_nothing_is_deleted_without_the_right_code(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path)
    store.create("Ghost Coast", "d")
    with pytest.raises(InvalidChangeError, match="nothing was deleted"):
        store.delete("Ghost Coast", "0000")
    with pytest.raises(NotFoundError, match="Known campaigns: Ghost Coast"):
        store.request_deletion("Ghost Cost")
    assert (tmp_path / "campaigns" / "Ghost Coast.json").exists()


@pytest.mark.anyio
async def test_delete_campaign_tool_asks_then_deletes(client: Client) -> None:
    await call(client, "create_campaign", name="Ghost Coast", description="d")
    await call(client, "create_character", name="Aria", character_class="Wizard", race="Elf")
    first = await call(client, "delete_campaign", name="Ghost Coast")
    assert first.startswith("Nothing deleted yet") and "1 characters" in first
    code = re.search(r"confirmation_code '(\d{4})'", first)
    assert code is not None
    assert "wrong or expired" in await call_error(
        client, "delete_campaign", name="Ghost Coast", confirmation_code="nope"
    )
    second = await call(client, "delete_campaign", name="Ghost Coast")
    code = re.search(r"confirmation_code '(\d{4})'", second)
    assert code is not None
    done = await call(
        client, "delete_campaign", name="Ghost Coast", confirmation_code=code.group(1)
    )
    assert "deleted" in done and "No campaign is active now" in done
    assert "No campaign saved yet" in await call(client, "list_campaigns")


@pytest.mark.anyio
async def test_list_campaigns_describes_each_one(client: Client) -> None:
    await call(client, "create_campaign", name="Ghost Coast", description="Fog and wrecks")
    await call(client, "create_character", name="Aria", character_class="Wizard", race="Elf")
    listing = await call(client, "list_campaigns")
    assert "Ghost Coast (active): Fog and wrecks. 1 characters, 0 quests, at session 1" in listing
