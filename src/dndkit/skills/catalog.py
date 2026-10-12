"""The skills in this package: their frontmatter, their files, and the digests of those.

A skill is a folder with a ``SKILL.md`` whose YAML frontmatter names it; the
name must be the folder's (Agent Skills specification). Every file under the
folder belongs to the skill. Files are read once, at load: the digests then
describe exactly what the server serves.
"""

import hashlib
import json
import mimetypes
from dataclasses import dataclass
from functools import cache
from importlib.resources import files
from importlib.resources.abc import Traversable
from typing import Any

import yaml

SKILL_FILE = "SKILL.md"
SCHEME = "skill://"


@dataclass(frozen=True)
class SkillFile:
    """One file of a skill, as served."""

    path: str  # relative to the skill's folder, "/"-separated
    content: bytes

    @property
    def digest(self) -> str:
        """``sha256:<hex>`` of the raw bytes (SEP-2640)."""
        return "sha256:" + hashlib.sha256(self.content).hexdigest()

    @property
    def mime_type(self) -> str:
        if self.path.endswith(".md"):
            return "text/markdown"
        return mimetypes.guess_type(self.path)[0] or "application/octet-stream"


@dataclass(frozen=True)
class Skill:
    """A skill: its frontmatter as written, and all its files."""

    name: str
    frontmatter: dict[str, Any]
    files: tuple[SkillFile, ...]

    @property
    def uri(self) -> str:
        """The URI of its ``SKILL.md``, which identifies the skill."""
        return self.file_uri(SKILL_FILE)

    def file_uri(self, path: str) -> str:
        return f"{SCHEME}{self.name}/{path}"

    def entry(self) -> dict[str, Any]:
        """Its ``skills/list`` entry: uri, verbatim frontmatter, every file's digest and size."""
        return {
            "uri": self.uri,
            "frontmatter": self.frontmatter,
            "resources": [
                {"uri": self.file_uri(f.path), "digest": f.digest, "size": len(f.content)}
                for f in self.files
            ],
        }


@cache
def load_catalog() -> tuple[Skill, ...]:
    """Every skill shipped in this package, by name."""
    root = files(__name__.rsplit(".", 1)[0])
    skills = [_load(folder) for folder in root.iterdir() if folder.joinpath(SKILL_FILE).is_file()]
    return tuple(sorted(skills, key=lambda s: s.name))


def frontmatter_of(text: str) -> dict[str, Any]:
    """The YAML frontmatter of a ``SKILL.md``, as a JSON-ready mapping: between a
    first line ``---`` and the next line that is ``---`` alone."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md must begin with YAML frontmatter.")
    end = next((i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"), None)
    if end is None:
        raise ValueError("SKILL.md frontmatter has no closing '---'.")
    data = yaml.safe_load("\n".join(lines[1:end]))
    if not isinstance(data, dict) or not data.get("name") or not data.get("description"):
        raise ValueError("SKILL.md frontmatter needs a name and a description.")
    # skills/list sends it as JSON: a YAML date becomes its text.
    return dict(json.loads(json.dumps(data, default=str)))


def _load(folder: Traversable) -> Skill:
    frontmatter = frontmatter_of(folder.joinpath(SKILL_FILE).read_text(encoding="utf-8"))
    if frontmatter["name"] != folder.name:
        raise ValueError(f"Skill folder {folder.name} holds a skill named {frontmatter['name']}.")
    found = sorted(_walk(folder, ""), key=lambda f: (f.path != SKILL_FILE, f.path))
    return Skill(name=folder.name, frontmatter=frontmatter, files=tuple(found))


def _walk(folder: Traversable, prefix: str) -> list[SkillFile]:
    found: list[SkillFile] = []
    for entry in folder.iterdir():
        if entry.name.startswith((".", "__")):
            continue
        path = f"{prefix}{entry.name}"
        if entry.is_dir():
            found += _walk(entry, f"{path}/")
        else:
            found.append(SkillFile(path, entry.read_bytes()))
    return found
