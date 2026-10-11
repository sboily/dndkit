"""The campaign store: one active campaign, saved as JSON, safe across threads."""

import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from gamemaster_mcp.errors import (
    AlreadyExistsError,
    GameError,
    InvalidChangeError,
    NoActiveCampaignError,
    NotFoundError,
)
from gamemaster_mcp.models import Campaign, GameState, now
from gamemaster_mcp.storage.files import campaign_slug, read_json, same_slug, write_json_atomic

logger = logging.getLogger(__name__)

SETTING_SUFFIXES = (".md", ".txt")
MAX_SETTING_BYTES = 200_000


@dataclass(frozen=True)
class CampaignEntry:
    """A campaign file and the campaign name stored in it."""

    name: str
    path: Path


class CampaignStore:
    """Holds the active campaign and writes every change to disk.

    FastMCP runs synchronous tools in a thread pool, and voice models often
    call several tools at once, so every access goes through one lock.
    """

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.campaigns_dir = data_dir / "campaigns"
        self.settings_dir = data_dir / "settings"
        self.campaigns_dir.mkdir(parents=True, exist_ok=True)
        self.settings_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._current: Campaign | None = None
        self._current_path: Path | None = None
        self._open_most_recent()

    @property
    def current(self) -> Campaign | None:
        """The active campaign, if any."""
        with self._lock:
            return self._current

    def list_campaigns(self) -> list[CampaignEntry]:
        """Every campaign file, by the name stored inside it."""
        with self._lock:
            paths = sorted(self.campaigns_dir.glob("*.json"))
            return [CampaignEntry(self._stored_name(path), path) for path in paths]

    def create(
        self,
        name: str,
        description: str,
        dm_name: str | None = None,
        setting: str | None = None,
    ) -> Campaign:
        """Create a campaign and make it active; an existing one is never replaced."""
        slug = campaign_slug(name)
        with self._lock:
            existing = self._file_for_slug(slug)
            if existing is not None:
                raise AlreadyExistsError(
                    f"A campaign named '{self._stored_name(existing)}' already exists. "
                    "Open it with load_campaign or pick another name."
                )
            title = name.strip()
            campaign = Campaign(
                name=title,
                description=description,
                dm_name=dm_name,
                setting=setting,
                game_state=GameState(campaign_name=title),
            )
            path = self.campaigns_dir / f"{slug}.json"
            self._write(campaign, path)
            self._current, self._current_path = campaign, path
            logger.info("Created campaign %r in %s", title, path)
            return campaign

    def load(self, name: str) -> Campaign:
        """Open a campaign by name and make it active."""
        with self._lock:
            path = self._file_for_slug(campaign_slug(name))
            if path is None:
                known = ", ".join(entry.name for entry in self.list_campaigns()) or "none yet"
                raise NotFoundError(f"No campaign named '{name}'. Known campaigns: {known}.")
            campaign = self._read(path)
            path.touch()  # the most recently opened campaign reopens at the next start
            self._current, self._current_path = campaign, path
            return campaign

    def read_setting_file(self, file_name: str) -> str:
        """Text of a .md/.txt file placed directly in the settings directory."""
        folder = self.settings_dir.resolve()
        candidate = (folder / file_name).resolve()
        if candidate.parent != folder or candidate.suffix.lower() not in SETTING_SUFFIXES:
            raise InvalidChangeError(
                f"A setting file is a .md or .txt file directly inside {folder}."
            )
        if not candidate.is_file():
            available = sorted(p.name for p in folder.iterdir() if p.suffix in SETTING_SUFFIXES)
            raise NotFoundError(
                f"No setting file '{file_name}' in {folder}. "
                f"Available: {', '.join(available) or 'none'}."
            )
        if candidate.stat().st_size > MAX_SETTING_BYTES:
            raise InvalidChangeError(f"'{file_name}' is over {MAX_SETTING_BYTES} bytes.")
        return candidate.read_text(encoding="utf-8")

    @contextmanager
    def transaction(self) -> Iterator[Campaign]:
        """The active campaign to change: saved on success, restored on any failure.

        A tool that fails halfway leaves nothing behind, in memory or on disk,
        so the model can retry without doubling an item or a hit.
        """
        with self._lock:
            campaign, path = self._require_current()
            snapshot = campaign.model_copy(deep=True)
            try:
                yield campaign
                campaign.updated_at = now()
                self._write(campaign, path)
            except BaseException:
                self._current = snapshot
                raise

    @contextmanager
    def reading(self) -> Iterator[Campaign]:
        """The active campaign, to read while no tool changes it."""
        with self._lock:
            campaign, _ = self._require_current()
            yield campaign

    def _require_current(self) -> tuple[Campaign, Path]:
        if self._current is None or self._current_path is None:
            raise NoActiveCampaignError()
        return self._current, self._current_path

    def _file_for_slug(self, slug: str) -> Path | None:
        for path in self.campaigns_dir.glob("*.json"):
            if same_slug(path.stem, slug):
                return path
        return None

    def _open_most_recent(self) -> None:
        paths = sorted(
            self.campaigns_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
        )
        for path in paths:
            try:
                self._current, self._current_path = self._read(path), path
            except GameError as exc:
                logger.error("Skipping campaign file %s: %s", path, exc)
                continue
            logger.info("Opened campaign %r from %s", self._current.name, path)
            return
        logger.info("No campaign to open in %s", self.campaigns_dir)

    @staticmethod
    def _read(path: Path) -> Campaign:
        try:
            return Campaign.model_validate(read_json(path))
        except (OSError, ValueError) as exc:  # JSONDecodeError and ValidationError included
            detail = str(exc)
            if isinstance(exc, ValidationError):
                first = exc.errors()[0]
                detail = f"{'.'.join(map(str, first['loc']))}: {first['msg']}"
            raise GameError(f"Campaign file {path.name} cannot be read: {detail}") from exc

    @staticmethod
    def _stored_name(path: Path) -> str:
        try:
            name = read_json(path).get("name")
        except (OSError, ValueError, AttributeError):
            return f"{path.stem} (unreadable)"
        return name if isinstance(name, str) and name else path.stem

    @staticmethod
    def _write(campaign: Campaign, path: Path) -> None:
        write_json_atomic(path, campaign.model_dump(mode="json"))
