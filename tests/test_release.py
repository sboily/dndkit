"""scripts/release.py: the changelog section a release publishes, and its stamp."""

import importlib.util
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


def test_the_changelog_has_a_section_for_every_release_to_come() -> None:
    text = (ROOT / "CHANGELOG.md").read_text()
    assert release.stamp(text, "0.4.0", date(2026, 10, 13)).startswith(
        "# Changelog\n\n## 0.4.0 (2026-10-13)\n"
    )
