"""scripts/release.py: the changelog section a release publishes, and its stamp."""

import importlib.util
import re
import tomllib
from datetime import date
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parents[1]


def load_release() -> ModuleType:
    spec = importlib.util.spec_from_file_location("release", ROOT / "scripts" / "release.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


release = load_release()

CHANGELOG = """# Changelog

## Unreleased

### Added

- Expertise.

## 0.4.1 (2026-11-01)

- A fix.

## 0.4.0 (2026-10-20)

- The rename.
"""


def test_notes_are_one_version_section() -> None:
    assert release.notes(CHANGELOG, "0.4.0") == "- The rename.\n"
    assert release.notes(CHANGELOG, "0.4.1") == "- A fix.\n"
    with pytest.raises(ValueError, match="no section for 0.4"):
        release.notes(CHANGELOG, "0.4")


def test_a_release_names_the_unreleased_section() -> None:
    stamped = release.stamp(CHANGELOG, "0.5.0", date(2026, 12, 1))
    assert "## Unreleased" not in stamped
    assert release.notes(stamped, "0.5.0") == "### Added\n\n- Expertise.\n"
    empty = "# Changelog\n\n## Unreleased\n\n## 0.4.0\n\n- The rename.\n"
    with pytest.raises(ValueError, match="empty: nothing to release"):
        release.stamp(empty, "0.5.0", date(2026, 12, 1))
    with pytest.raises(ValueError, match="no '## Unreleased' section"):
        release.stamp(stamped, "0.6.0", date(2026, 12, 2))


def test_the_changelog_opens_on_what_comes_next_or_on_this_version() -> None:
    """Between releases, an Unreleased section ready to stamp; on a release's own
    commit, that version's section, which the GitHub release takes as its notes."""
    text = (ROOT / "CHANGELOG.md").read_text()
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    first = re.search(r"^## (.+)$", text, re.MULTILINE)
    assert first is not None
    if first.group(1) == "Unreleased":
        assert release.stamp(text, "9.9.9", date(2026, 10, 13))
    else:
        assert first.group(1).startswith(f"{version} ("), first.group(1)
        assert release.notes(text, version).strip()
