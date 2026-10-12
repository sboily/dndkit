"""The middleware that writes every tool call and skill read to the activity log.

The widgets' own data calls (``get_screen_data``, every second or two) are
left out: they say nothing about what the model does.
"""

import json
import time
from typing import Any

from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.base import ToolResult
from mcp import types as mt

from gamemaster_mcp.activity import ActivityLog

QUIET_TOOLS = frozenset({"get_screen_data"})


class Recorder(Middleware):
    """Records the model's calls in *log*."""

    def __init__(self, log: ActivityLog) -> None:
        self.log = log

    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        name = context.message.name
        if name in QUIET_TOOLS:
            return await call_next(context)
        arguments = json.dumps(context.message.arguments or {}, ensure_ascii=False)
        started = time.perf_counter()
        try:
            result = await call_next(context)
        except Exception as exc:
            self.log.record("tool", name, arguments, str(exc), True, started)
            raise
        self.log.record("tool", name, arguments, _text(result), False, started)
        return result

    async def on_read_resource(
        self,
        context: MiddlewareContext[mt.ReadResourceRequestParams],
        call_next: CallNext[mt.ReadResourceRequestParams, Any],
    ) -> Any:
        uri = str(context.message.uri)
        if not uri.startswith("skill://"):
            return await call_next(context)
        started = time.perf_counter()
        try:
            result = await call_next(context)
        except Exception as exc:
            self.log.record("skill", "resources/read", uri, str(exc), True, started)
            raise
        self.log.record("skill", "resources/read", uri, "read", False, started)
        return result


def _text(result: ToolResult) -> str:
    return "\n".join(getattr(block, "text", "") for block in result.content)
