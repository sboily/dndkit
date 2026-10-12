"""Who opens what: each character's private link, the backstage's, and where
phones find the server.

A player's link carries a token derived from the campaign, the character and
a secret kept in the data directory: links survive restarts, cannot be
guessed, and all change if that file is deleted. The backstage's link, for a
game master away from the server's computer (Docker, a home server), is
derived from the same secret.
"""

import base64
import functools
import hashlib
import hmac
import ipaddress
import os
import re
import secrets
import socket
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import segno

from dndkit.config import WebSettings
from dndkit.models import Campaign, Character
from dndkit.views.everyone import Json

KEY_FILE = "player-links.key"
SECRET_BYTES = 32
TOKEN_BYTES = 10  # 80 bits, 16 base32 characters
TOKEN_PATTERN = re.compile(r"[a-z2-7]{16}")
BACKSTAGE = b"backstage"  # no campaign/character pair looks like it


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
        return self._sign(f"{campaign.id}/{character.id}".encode())

    def backstage_token(self) -> str:
        """The token in the backstage's link, the same for every campaign."""
        return self._sign(BACKSTAGE)

    def opens_backstage(self, token: str) -> bool:
        return bool(TOKEN_PATTERN.fullmatch(token)) and hmac.compare_digest(
            self.backstage_token(), token
        )

    def _sign(self, message: bytes) -> str:
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


@dataclass(frozen=True)
class Invitations:
    """The join codes away from any page (the MCP widget), at the address phones use:
    the configured one, else this computer's on the network, else none they reach."""

    links: PlayerLinks
    settings: WebSettings
    local_url: str  # where the pages answer on this machine

    def view(self, campaign: Campaign) -> Json:
        phones, reachable = phone_base_url(self.settings, self.local_url)
        return join(campaign, self.links, phones, reachable)


def join(campaign: Campaign, links: PlayerLinks, base_url: str, reachable: bool) -> Json:
    """Each character's link and its QR code, for the table screen."""
    players = []
    for character in sorted(campaign.characters.values(), key=lambda c: c.name):
        url = f"{base_url}/p/{links.token(campaign, character)}/"
        players.append(
            {"name": character.name, "player": character.player_name, "url": url, "qr": _qr(url)}
        )
    return {"reachable": reachable, "players": players}


@functools.lru_cache(maxsize=64)
def _qr(url: str) -> str:
    """A link's QR code as an image URI; the same links come back at every change."""
    return segno.make(url, error="m").svg_data_uri(scale=4, dark="#1d1a22", light="#ffffff")


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
