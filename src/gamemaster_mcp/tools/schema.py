"""Compact the JSON schemas advertised to clients.

An optional parameter (``int | None = None``) is advertised by Pydantic as
``{"anyOf": [{"type": "integer"}, {"type": "null"}], "default": null}``. A
model leaves an optional parameter out rather than sending null, so the
advertised form keeps only the real type: about a third fewer schema tokens,
which keeps the catalogue under roomkit's Tool Search threshold, and no
``anyOf`` for Gemini to stumble on. Validation is untouched: FastMCP checks
calls against the Python signature, which still accepts null.
"""

from typing import Any

_NULL = {"type": "null"}


def compact(schema: dict[str, Any]) -> dict[str, Any]:
    """A copy of *schema* with nullable optionals reduced to their real type."""
    result = dict(schema)
    properties = schema.get("properties")
    if isinstance(properties, dict):
        result["properties"] = {name: _property(prop) for name, prop in properties.items()}
    items = schema.get("items")
    if isinstance(items, dict):
        result["items"] = compact(items)
    definitions = schema.get("$defs")
    if isinstance(definitions, dict):  # models such as Participant; FastMCP inlines them later
        result["$defs"] = {name: compact(d) for name, d in definitions.items()}
    return result


def _property(prop: dict[str, Any]) -> dict[str, Any]:
    variants = prop.get("anyOf")
    if isinstance(variants, list) and len(variants) == 2 and _NULL in variants:
        real = next(v for v in variants if v != _NULL)
        rest = {key: value for key, value in prop.items() if key != "anyOf"}
        if rest.get("default", ...) is None:
            del rest["default"]
        prop = {**real, **rest}
    return compact(prop)
