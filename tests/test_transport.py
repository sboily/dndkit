"""The server over HTTP: its settings, its token, and a real run of it."""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

from dndkit.config import HttpSettings, SettingsError, resolve_http_settings
from dndkit.transport import BearerToken
from tests.helpers import call

pytestmark = pytest.mark.anyio
TOKEN = "a-token-of-thirty-two-characters"


def test_stdio_unless_asked_and_a_token_beyond_this_machine() -> None:
    assert resolve_http_settings({}) is None
    assert resolve_http_settings({"DNDKIT_TRANSPORT": "STDIO"}) is None
    assert resolve_http_settings({"DNDKIT_TRANSPORT": "http"}) == HttpSettings()
    everywhere = {"DNDKIT_TRANSPORT": "http", "DNDKIT_HTTP_HOST": "0.0.0.0"}  # nosec B104
    with pytest.raises(SettingsError, match="set DNDKIT_HTTP_TOKEN"):
        resolve_http_settings(everywhere)
    settings = resolve_http_settings(
        everywhere | {"DNDKIT_HTTP_PORT": "9000", "DNDKIT_HTTP_TOKEN": TOKEN}
    )
    assert settings == HttpSettings("0.0.0.0", 9000, TOKEN)  # nosec B104
    for wrong, message in (
        ({"DNDKIT_TRANSPORT": "sse"}, "stdio or http"),
        ({"DNDKIT_TRANSPORT": "http", "DNDKIT_HTTP_PORT": "80000"}, "not a port"),
        ({"DNDKIT_TRANSPORT": "http", "DNDKIT_HTTP_TOKEN": "short"}, "16 characters"),
    ):
        with pytest.raises(SettingsError, match=message):
            resolve_http_settings(wrong)


async def test_the_bearer_token_is_the_server_s_own() -> None:
    verifier = BearerToken(TOKEN)
    assert (await verifier.verify_token(TOKEN)) is not None
    assert (await verifier.verify_token(TOKEN[:-1] + "x")) is None


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
        return port


async def test_a_server_of_its_own_over_http(tmp_path: Path) -> None:
    port = _free_port()
    env = os.environ | {
        "DNDKIT_TRANSPORT": "http",
        "DNDKIT_HTTP_PORT": str(port),
        "DNDKIT_HTTP_TOKEN": TOKEN,
        "DNDKIT_STORAGE_DIR": str(tmp_path),
    }
    command = [sys.executable, "-c", "from dndkit.app import main; main()"]
    server = subprocess.Popen(command, env=env, stderr=subprocess.DEVNULL)  # nosec B603
    base = f"http://127.0.0.1:{port}"
    try:
        _wait_for(f"{base}/health")
        refused = httpx.post(f"{base}/mcp", json={}, headers={"accept": "application/json"})
        assert refused.status_code == 401
        auth = {"Authorization": f"Bearer {TOKEN}"}
        async with Client(StreamableHttpTransport(f"{base}/mcp", headers=auth)) as first:
            await call(first, "create_campaign", name="Far away", description="d")
        async with Client(StreamableHttpTransport(f"{base}/mcp", headers=auth)) as second:
            assert "Far away (active)" in await call(second, "list_campaigns")
    finally:
        server.terminate()
        server.wait(timeout=10)


def _wait_for(url: str) -> None:
    for _ in range(100):
        try:
            if httpx.get(url).text == "ok":
                return
        except httpx.TransportError:
            pass
        time.sleep(0.1)
    raise AssertionError(f"{url} never answered")
