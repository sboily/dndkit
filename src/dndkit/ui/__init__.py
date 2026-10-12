"""The pages: MCP Apps widgets and the web pages.

Each ``<name>.html`` holds one page; the shared styles and scripts replace its
``<!--gm:shared-->`` marker, so every page served is self-contained:
roomkit-ui serves a widget's HTML alone, relative URLs 404, and sessions may
be offline. A web page also gets ``window.GM_WEB``, which makes ``shared.js``
read the server's event stream instead of calling MCP tools.

The scripts are written as ES modules, so tools (knip) can follow who uses
what; a page inlines them as one classic script, their import lines dropped and
their exports left as plain declarations, in ``SCRIPTS`` order (a module after
those it imports).
"""

import re
from functools import cache
from importlib.resources import files

_MARKER = "<!--gm:shared-->"
_STYLES = ("shared.css", "components.css")
SCRIPTS = (
    "words.js",
    "shared.js",
    "dicetray.js",
    "battlemap.js",
    "backstage.js",
    "world.js",
    "sheet.js",
    "desk.js",
    "components.js",
)
_WEB = '<script>window.GM_WEB = { feed: "feed" };</script>\n'
IMPORT = re.compile(r'^import \{[^}]*\} from "\./([\w-]+\.js)";\n', re.MULTILINE)
_EXPORT = re.compile(r"^export (?=(?:const|function|class) )", re.MULTILINE)


@cache
def page(name: str, web: bool = False) -> str:
    """The complete HTML of page *name*; *web* for a page served by the web server."""
    css = "".join(_read(style) for style in _STYLES)
    js = "\n".join(_inline(_read(script)) for script in SCRIPTS)
    shared = f"<style>\n{css}</style>\n{_WEB if web else ''}<script>\n{js}</script>"
    return _read(f"{name}.html").replace(_MARKER, shared, 1)


def _inline(module: str) -> str:
    """A module as part of the page's one classic script."""
    return _EXPORT.sub("", IMPORT.sub("", module))


def _read(name: str) -> str:
    return files(__name__).joinpath(name).read_text(encoding="utf-8")
