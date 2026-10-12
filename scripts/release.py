"""Releases: the changelog's sections, and the local half of a release.

    uv run python scripts/release.py prepare 0.5.0   # on main: version, changelog, commit, tag
    uv run python scripts/release.py notes 0.5.0     # that version's changelog section

Changes go under ``## Unreleased`` in CHANGELOG.md as they land. ``prepare``
turns that heading into ``## 0.5.0 (date)``, sets the version, commits and
tags ``v0.5.0``; pushing the tag runs ``.github/workflows/release.yml``, which
publishes to PyPI and makes the GitHub release from ``notes``.
"""

import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = ROOT / "CHANGELOG.md"
UNRELEASED = "## Unreleased"
VERSION = re.compile(r"\d+\.\d+\.\d+")


def notes(changelog: str, version: str) -> str:
    """The body of *version*'s section, without its heading; an error if there is none."""
    body = _section(changelog, rf"{re.escape(version)}(?=\s|$)")
    if body is None:
        raise ValueError(f"CHANGELOG.md has no section for {version}.")
    return body


def stamp(changelog: str, version: str, day: date) -> str:
    """The changelog with its Unreleased section named after *version* and *day*."""
    body = _section(changelog, "Unreleased$")
    if body is None:
        raise ValueError(f"CHANGELOG.md has no '{UNRELEASED}' section to release.")
    if not body.strip():
        raise ValueError(f"The '{UNRELEASED}' section is empty: nothing to release.")
    heading = re.compile(r"^## Unreleased$", re.MULTILINE)
    return heading.sub(f"## {version} ({day.isoformat()})", changelog, count=1)


def _section(changelog: str, title: str) -> str | None:
    """The text under the first ``## <title>`` heading, up to the next one."""
    found = re.search(rf"^## {title}.*$", changelog, re.MULTILINE)
    if found is None:
        return None
    following = re.search(r"^## ", changelog[found.end() :], re.MULTILINE)
    end = found.end() + following.start() if following else len(changelog)
    return changelog[found.end() : end].strip() + "\n"


def git(*args: str) -> str:
    done = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True)
    return done.stdout.strip()


def prepare(version: str) -> None:
    """Version, changelog, a commit and an annotated tag, on a clean main; nothing pushed."""
    if git("branch", "--show-current") != "main":
        raise SystemExit("Release from main.")
    if git("status", "--porcelain"):
        raise SystemExit("Commit or stash your changes first.")
    if git("tag", "--list", f"v{version}"):
        raise SystemExit(f"v{version} already exists.")
    CHANGELOG.write_text(stamp(CHANGELOG.read_text(), version, date.today()))
    subprocess.run(["uv", "version", version, "--no-sync"], cwd=ROOT, check=True)
    git("commit", "-am", f"release: {version}")
    git("tag", "-a", f"v{version}", "-m", f"dndkit {version}")
    print(f"Tagged v{version}. To publish: git push origin main v{version}")


def main(argv: list[str]) -> None:
    if len(argv) != 2 or argv[0] not in ("prepare", "notes") or not VERSION.fullmatch(argv[1]):
        raise SystemExit(__doc__)
    command, version = argv
    try:
        if command == "notes":
            sys.stdout.write(notes(CHANGELOG.read_text(), version))
        else:
            prepare(version)
    except ValueError as error:
        raise SystemExit(str(error)) from None


if __name__ == "__main__":
    main(sys.argv[1:])
