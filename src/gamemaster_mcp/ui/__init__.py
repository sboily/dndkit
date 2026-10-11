"""The pages: MCP Apps widgets and the web pages.

Each ``<name>.html`` holds one page; the shared styles and scripts replace its
``<!--gm:shared-->`` marker, so every page served is self-contained:
roomkit-ui serves a widget's HTML alone, relative URLs 404, and sessions may
be offline. A web page also gets ``window.GM_WEB``, which makes ``shared.js``
read the server's event stream instead of calling MCP tools.
"""

from functools import cache
from importlib.resources import files

_MARKER = "<!--gm:shared-->"
_STYLES = ("shared.css", "components.css")
_SCRIPTS = ("words.js", "shared.js", "dicetray.js", "components.js")
_WEB = '<script>window.GM_WEB = { feed: "feed" };</script>\n'


@cache
def page(name: str, web: bool = False) -> str:
    """The complete HTML of page *name*; *web* for a page served by the web server."""
    css = "".join(_read(style) for style in _STYLES)
    js = "\n".join(_read(script) for script in _SCRIPTS)
    shared = f"<style>\n{css}</style>\n{_WEB if web else ''}<script>\n{js}</script>"
    return _read(f"{name}.html").replace(_MARKER, shared, 1)


def _read(name: str) -> str:
    return files(__name__).joinpath(name).read_text(encoding="utf-8")
