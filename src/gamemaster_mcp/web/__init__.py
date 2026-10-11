"""Web pages that follow the game live: the table screen, players' phones, the backstage.

They run inside the MCP server's process (``server.web_pages``) and read the
same campaign store and dice log as the tools, so a change shows at once.
"""

from gamemaster_mcp.web.changes import Changes
from gamemaster_mcp.web.server import web_pages

__all__ = ["Changes", "web_pages"]
