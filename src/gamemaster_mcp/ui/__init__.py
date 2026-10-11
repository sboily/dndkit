"""Pages for the MCP Apps widgets.

Each ``<name>.html`` holds one app; ``shared.css`` and ``shared.js`` (the
host bridge) replace its ``<!--gm:shared-->`` marker, so every served page is
self-contained: roomkit-ui serves the HTML alone and relative URLs 404.
"""

from functools import cache
from importlib.resources import files

_MARKER = "<!--gm:shared-->"


@cache
def page(name: str) -> str:
    """The complete HTML of app *name*."""
    folder = files(__name__)
    html = folder.joinpath(f"{name}.html").read_text(encoding="utf-8")
    css = folder.joinpath("shared.css").read_text(encoding="utf-8")
    js = folder.joinpath("shared.js").read_text(encoding="utf-8")
    return html.replace(_MARKER, f"<style>\n{css}</style>\n<script>\n{js}</script>", 1)
