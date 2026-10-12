"""Sharing the data directory with another process: a second MCP client, a
restart that overlaps the old server, a campaign file edited by hand.

Changes take turns through an advisory lock on ``<data dir>/.lock``, and the
store reads the active campaign again whenever its file changed since it last
read or wrote it. Every change is saved at once, so reading the file again
loses nothing of ours; without it, each process would overwrite the other's
changes with its own copy.
"""

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import IO

LOCK_FILE = ".lock"


@dataclass(frozen=True)
class Stamp:
    """What tells two versions of a file apart: an atomic write makes a new inode."""

    inode: int
    modified_ns: int
    size: int


def stamp(path: Path) -> Stamp | None:
    """*path*'s stamp, or None when it is gone."""
    try:
        info = path.stat()
    except OSError:
        return None
    return Stamp(info.st_ino, info.st_mtime_ns, info.st_size)


class DiskLock:
    """An exclusive advisory lock across processes (none on Windows, where the
    stamps alone catch a change made elsewhere)."""

    def __init__(self, data_dir: Path) -> None:
        self._path = data_dir / LOCK_FILE
        self._file: IO[bytes] | None = None

    @contextmanager
    def held(self) -> Iterator[None]:
        """Hold the lock for a change; another process waits its turn."""
        if sys.platform == "win32":
            yield
            return
        import fcntl

        if self._file is None:
            self._file = open(self._path, "ab")  # noqa: SIM115 - kept open, like the lock
        fcntl.flock(self._file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)

    def close(self) -> None:
        """Let go of the lock file (the process's end does it too)."""
        if self._file is not None:
            self._file.close()
            self._file = None
