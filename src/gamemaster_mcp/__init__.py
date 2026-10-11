"""Gamemaster MCP: a D&D 5e campaign server for voice and chat game masters."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("gamemaster-mcp")
except PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "0.0.0"

__all__ = ["__version__"]
