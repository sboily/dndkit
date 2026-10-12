"""The shipped skills, published by the MCP Skills extension (SEP-2640)."""

import hashlib
from typing import Any, ClassVar

import pytest
from fastmcp import Client
from mcp.shared.exceptions import MCPError
from pydantic import BaseModel, TypeAdapter

from dndkit.skills import load_catalog
from dndkit.skills.catalog import frontmatter_of
from dndkit.skills.extension import IDENTIFIER

pytestmark = pytest.mark.anyio


class Raw(BaseModel):
    """A request for a method the SDK has no model for."""

    name_param: ClassVar[str | None] = None
    method: str
    params: dict[str, Any] | None = None


async def ask(client: Client, method: str, **params: Any) -> dict[str, Any]:
    result: dict[str, Any] = await client.session.send_request(
        Raw(method=method, params=params), TypeAdapter(dict[str, Any])
    )
    return result


def test_each_skill_is_named_after_its_folder() -> None:
    skills = {s.name: s for s in load_catalog()}
    assert set(skills) == {"dnd-battle-map", "dnd-game-master", "dnd-monsters"}
    for skill in skills.values():
        assert skill.frontmatter["name"] == skill.name and skill.frontmatter["description"]
        assert skill.files[0].path == "SKILL.md"
        assert skill.uri == f"skill://{skill.name}/SKILL.md"


def test_frontmatter_is_required() -> None:
    with pytest.raises(ValueError, match="begin with YAML"):
        frontmatter_of("# No frontmatter")
    with pytest.raises(ValueError, match="name and a description"):
        frontmatter_of("---\nname: x\n---\nbody")
    with pytest.raises(ValueError, match="no closing"):
        frontmatter_of("---\nname: x\n")
    dashed = "---\nname: x\ndescription: a---b\nupdated: 2026-01-02\n---\nbody --- here"
    assert frontmatter_of(dashed) == {"name": "x", "description": "a---b", "updated": "2026-01-02"}


async def test_the_server_declares_the_extension(client: Client) -> None:
    capabilities = client.server_capabilities
    assert capabilities is not None and capabilities.resources is not None
    assert IDENTIFIER in (capabilities.extensions or {})


async def test_listed_digests_match_what_resources_read_returns(client: Client) -> None:
    listed = await ask(client, "skills/list")
    assert [s["frontmatter"]["name"] for s in listed["skills"]] == [
        "dnd-battle-map",
        "dnd-game-master",
        "dnd-monsters",
    ]
    for entry in listed["skills"]:
        for resource in entry["resources"]:
            text = (await client.read_resource(resource["uri"]))[0].text  # type: ignore[union-attr]
            raw = text.encode("utf-8")
            assert len(raw) == resource["size"]
            assert resource["digest"] == "sha256:" + hashlib.sha256(raw).hexdigest()
        skill_md = (await client.read_resource(entry["uri"]))[0].text  # type: ignore[union-attr]
        assert frontmatter_of(skill_md) == entry["frontmatter"]  # verbatim


async def test_a_skill_is_retrieved_by_its_uri(client: Client) -> None:
    got = await ask(client, "skills/get", uri="skill://dnd-monsters/SKILL.md")
    assert got["skill"]["frontmatter"]["allowed_tools"] == ["save_monster", "plan_encounter"]
    with pytest.raises(MCPError) as refused:
        await ask(client, "skills/get", uri="skill://dragons/SKILL.md")
    assert refused.value.code == -32602


async def test_resources_carry_the_skill_metadata(client: Client) -> None:
    resources = {str(r.uri): r for r in await client.list_resources()}
    main = resources["skill://dnd-monsters/SKILL.md"]
    assert (main.name, main.mime_type) == ("dnd-monsters", "text/markdown")
    assert (main.description or "").startswith("Create the monsters and bosses")
