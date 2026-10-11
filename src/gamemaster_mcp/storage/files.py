"""File primitives: campaign file names and crash-safe JSON writes."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from gamemaster_mcp.errors import InvalidChangeError

_NAME_CHARS = (" ", "-", "_")


def campaign_slug(name: str) -> str:
    """The file stem for a campaign name: letters, digits, spaces, '-' and '_'.

    It cannot leave the campaigns directory: '/', '\\' and '.' never survive.
    """
    kept = "".join(c for c in name if c.isalnum() or c in _NAME_CHARS)
    slug = " ".join(kept.split())
    if not slug:
        raise InvalidChangeError(f"Campaign name '{name}' needs at least one letter or digit.")
    return slug


def same_slug(a: str, b: str) -> bool:
    """Two stems that name one file on a case-insensitive disk (macOS, Windows)."""
    return a.casefold() == b.casefold()


def write_json_atomic(path: Path, data: Any) -> None:
    """Write JSON so a crash leaves either the old file or the new one, never half.

    The temporary file sits next to the target (same filesystem, so the rename
    is atomic) and ends in ``.tmp``, which the ``*.json`` scans never pick up.
    """
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.stem}.", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=1)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def read_json(path: Path) -> Any:
    """Parse one JSON file."""
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)
