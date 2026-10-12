"""Shared fixtures: an isolated data directory, a store, an MCP client."""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fastmcp import Client

from dndkit.app import build_server
from dndkit.storage import CampaignStore


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def store(tmp_path: Path) -> CampaignStore:
    """A store with an active, empty campaign."""
    campaign_store = CampaignStore(tmp_path)
    campaign_store.create("Test Campaign", "For tests")
    return campaign_store


@pytest.fixture
async def client(tmp_path: Path) -> AsyncIterator[Client]:
    """An in-memory MCP client on a server whose data lives in tmp_path."""
    async with Client(build_server(tmp_path)) as connected:
        yield connected
