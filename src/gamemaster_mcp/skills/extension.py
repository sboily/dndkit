"""The skills over MCP (SEP-2640, ``io.modelcontextprotocol/skills``).

Every file of every skill is a resource, ``skill://<name>/<path>``, read with
``resources/read``. ``skills/list`` gives each skill's entry (its ``SKILL.md``
URI, its frontmatter verbatim, and every file with its SHA-256 digest and
size), and ``skills/get`` one entry by URI. The catalogue is small and fixed,
so the listing is complete in one page.
"""

from collections.abc import Callable, Sequence
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.extensions import MethodBinding, ServerExtension
from mcp.server.context import ServerRequestContext
from mcp.shared.exceptions import MCPError
from mcp_types import PaginatedRequestParams, RequestParams
from mcp_types.jsonrpc import INVALID_PARAMS

from gamemaster_mcp.skills.catalog import SKILL_FILE, Skill, SkillFile, load_catalog

IDENTIFIER = "io.modelcontextprotocol/skills"


class SkillParams(RequestParams):
    """``skills/get``: the URI of a skill's ``SKILL.md``."""

    uri: str


class SkillsExtension(ServerExtension):
    """Serves ``skills/list`` and ``skills/get`` over the skills given."""

    identifier = IDENTIFIER

    def __init__(self, skills: Sequence[Skill]) -> None:
        self._skills = tuple(skills)

    def methods(self) -> Sequence[MethodBinding]:
        return (
            MethodBinding("skills/list", PaginatedRequestParams, self.list_skills),
            MethodBinding("skills/get", SkillParams, self.get_skill),
        )

    async def list_skills(
        self, _ctx: ServerRequestContext[Any, Any], _params: PaginatedRequestParams
    ) -> dict[str, Any]:
        """Every skill's entry."""
        return {"resultType": "complete", "skills": [s.entry() for s in self._skills]}

    async def get_skill(
        self, _ctx: ServerRequestContext[Any, Any], params: SkillParams
    ) -> dict[str, Any]:
        """One skill's entry; an unknown URI is invalid params, as for resources/read."""
        for skill in self._skills:
            if skill.uri == params.uri:
                return {"resultType": "complete", "skill": skill.entry()}
        known = ", ".join(s.uri for s in self._skills)
        raise MCPError(INVALID_PARAMS, f"No skill at {params.uri}. Skills: {known}.")


def register_skills(server: FastMCP) -> None:
    """Serve the package's skills: their files as resources, and the extension."""
    skills = load_catalog()
    for skill in skills:
        for file in skill.files:
            main = file.path == SKILL_FILE
            server.resource(
                skill.file_uri(file.path),
                name=skill.name if main else f"{skill.name}/{file.path}",
                description=str(skill.frontmatter["description"]) if main else None,
                mime_type=file.mime_type,
            )(_reader(skill, file))
    server.add_extension(SkillsExtension(skills))


def _reader(skill: Skill, file: SkillFile) -> Callable[[], str | bytes]:
    def read() -> str | bytes:
        # Text goes back as it is stored, so the bytes match the published digest.
        return file.content.decode("utf-8") if file.mime_type.startswith("text/") else file.content

    read.__name__ = f"skill_{skill.name}_{file.path}".replace("-", "_").replace("/", "_")
    return read
