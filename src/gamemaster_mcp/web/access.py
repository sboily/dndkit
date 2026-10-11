"""Who opens what: each character's private link, and where phones find the server.

A player's link carries a token derived from the campaign, the character and
a secret kept in the data directory: links survive restarts, cannot be
guessed, and all change if that file is deleted.
"""

import base64
import hashlib
import hmac
import ipaddress
import os
import re
import secrets
import socket
from pathlib import Path
from urllib.parse import urlsplit

import segno

from gamemaster_mcp.config import WebSettings
from gamemaster_mcp.models import Campaign, Character
from gamemaster_mcp.views.widgets import Json

KEY_FILE = "player-links.key"
SECRET_BYTES = 32
TOKEN_BYTES = 10  # 80 bits, 16 base32 characters
TOKEN_PATTERN = re.compile(r"[a-z2-7]{16}")


class PlayerLinks:
    """The token in each character's link."""

    def __init__(self, secret: bytes) -> None:
        self._secret = secret

    @classmethod
    def open(cls, data_dir: Path) -> "PlayerLinks":
        """Links signed with the data directory's secret, created on first use."""
        return cls(_load_secret(data_dir / KEY_FILE))

    def token(self, campaign: Campaign, character: Character) -> str:
        """The token for *character* of *campaign*."""
        message = f"{campaign.id}/{character.id}".encode()
        digest = hmac.new(self._secret, message, hashlib.sha256).digest()
        return base64.b32encode(digest[:TOKEN_BYTES]).decode().lower()

    def character_for(self, campaign: Campaign, token: str) -> Character | None:
        """The character of *campaign* whose link carries *token*, if any."""
        if not TOKEN_PATTERN.fullmatch(token):
            return None
        for character in campaign.characters.values():
            if hmac.compare_digest(self.token(campaign, character), token):
                return character
        return None


def join(campaign: Campaign, links: PlayerLinks, base_url: str, reachable: bool) -> Json:
    """Each character's link and its QR code, for the table screen."""
    players = []
    for character in sorted(campaign.characters.values(), key=lambda c: c.name):
        url = f"{base_url}/p/{links.token(campaign, character)}/"
        qr = segno.make(url, error="m").svg_data_uri(scale=4, dark="#1d1a22", light="#ffffff")
        players.append(
            {"name": character.name, "player": character.player_name, "url": url, "qr": qr}
        )
    return {"reachable": reachable, "players": players}


def phone_base_url(settings: WebSettings, base_url: str) -> tuple[str, bool]:
    """The address phones should use, and whether they can reach it at all.

    *base_url* is the one the table screen used. A loopback one (the screen
    runs on this machine) becomes the LAN address when the server listens on
    every interface; otherwise phones cannot reach a loopback server.
    """
    if settings.public_url:
        return settings.public_url, True
    parts = urlsplit(base_url)
    own = base_url.rstrip("/")
    if not is_loopback(parts.hostname or ""):
        return own, True
    lan = lan_address() if _is_unspecified(settings.host) else None
    if lan is None:
        return own, False
    port = f":{parts.port}" if parts.port else ""
    return f"{parts.scheme}://{lan}{port}", True


def lan_address() -> str | None:
    """This machine's IPv4 address on the local network; nothing is sent."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect(("192.0.2.1", 9))  # TEST-NET-1: only picks the outgoing interface
            address: str = probe.getsockname()[0]
        except OSError:
            return None
    return None if is_loopback(address) else address


def is_loopback(host: str) -> bool:
    """True for this machine's own addresses: a request from it, or a URL to it."""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _is_unspecified(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_unspecified
    except ValueError:
        return host == ""


def _load_secret(path: Path) -> bytes:
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        with os.fdopen(os.open(path, flags, 0o600), "wb") as file:
            secret = secrets.token_bytes(SECRET_BYTES)
            file.write(secret)
            return secret
    except FileExistsError:
        secret = path.read_bytes()
    if len(secret) < SECRET_BYTES:  # a write cut short: start again, links change
        path.unlink()
        return _load_secret(path)
    return secret
