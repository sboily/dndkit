"""Agent Skills shipped with the server, and their publication over MCP.

Each folder here holding a ``SKILL.md`` is a skill (agentskills.io). The
server publishes them by the MCP Skills extension (SEP-2640,
``io.modelcontextprotocol/skills``): every file as a ``skill://<name>/<path>``
resource, and the ``skills/list`` and ``skills/get`` methods. A skill's
``allowed_tools`` frontmatter is roomkit's: it keeps those tools out of the
model's catalogue until the skill is activated.
"""

from dndkit.skills.catalog import Skill, load_catalog
from dndkit.skills.extension import SkillsExtension, register_skills

__all__ = ["Skill", "SkillsExtension", "load_catalog", "register_skills"]
