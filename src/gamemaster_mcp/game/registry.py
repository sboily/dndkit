"""Find, add, change and remove campaign entities by ID or by spoken name.

A voice transcript rarely spells a name the way it was typed ("aria",
"Élodie" heard as "Elodie"), so names match without case or accents. When
nothing matches, the error lists the known names so the model can retry.
"""

import unicodedata
from collections.abc import Iterable, Mapping, MutableMapping
from typing import Any, Protocol, cast

from pydantic import BaseModel, ValidationError

from gamemaster_mcp.errors import AlreadyExistsError, InvalidChangeError, NotFoundError


class Named(Protocol):
    """An entity with an ID and a display name."""

    @property
    def id(self) -> str: ...

    @property
    def name(self) -> str: ...


def normalize(name: str) -> str:
    """Casefolded, accent-free, single-spaced: how two spellings of a name compare."""
    decomposed = unicodedata.normalize("NFKD", name)
    bare = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(bare.casefold().split())


def known_names(entities: Iterable[Named]) -> str:
    """Sorted names for an error message."""
    names = sorted(entity.name for entity in entities)
    return ", ".join(names) if names else "none yet"


def find[E: Named](items: Mapping[str, E], ref: str, kind: str) -> E:
    """The entity whose ID or name is *ref*, or the only one whose name contains it.

    Spoken names get shortened ("the lighthouse" for "The Dark Lighthouse"): a
    part of a name (3 characters or more) is enough when no other name shares it.
    """
    if ref in items:
        return items[ref]
    wanted = normalize(ref)
    for entity in items.values():
        if normalize(entity.name) == wanted:
            return entity
    partial = [e for e in items.values() if len(wanted) >= 3 and wanted in normalize(e.name)]
    if len(partial) == 1:
        return partial[0]
    raise NotFoundError(f"No {kind} named '{ref}'. Known {kind}s: {known_names(items.values())}.")


def find_optional[E: Named](items: Mapping[str, E], ref: str) -> E | None:
    """The entity *ref* names, or None."""
    try:
        return find(items, ref, "entity")
    except NotFoundError:
        return None


def find_many[E: Named](items: Mapping[str, E], refs: Iterable[str], kind: str) -> list[E]:
    """Every entity in *refs*, or one error naming all the unknown ones."""
    found: list[E] = []
    missing: list[str] = []
    for ref in refs:
        try:
            entity = find(items, ref, kind)
        except NotFoundError:
            missing.append(ref)
            continue
        if entity not in found:
            found.append(entity)
    if missing:
        unknown = ", ".join(f"'{ref}'" for ref in missing)
        raise NotFoundError(
            f"Unknown {kind}s: {unknown}. Known {kind}s: {known_names(items.values())}."
        )
    return found


def ensure_name_free(
    items: Mapping[str, Named], name: str, kind: str, *, exclude_id: str | None = None
) -> None:
    """Refuse a name another entity of this kind already answers to."""
    wanted = normalize(name)
    if not wanted:
        raise InvalidChangeError(f"A {kind} needs a name.")
    for entity in items.values():
        if entity.id != exclude_id and normalize(entity.name) == wanted:
            raise AlreadyExistsError(
                f"A {kind} named '{entity.name}' already exists (id {entity.id}). "
                "Update that one, or choose another name."
            )


def add[E: Named](items: MutableMapping[str, E], entity: E, kind: str) -> E:
    """Store a new entity under its ID; its name must be free."""
    ensure_name_free(items, entity.name, kind)
    items[entity.id] = entity
    return entity


def remove[E: Named](items: MutableMapping[str, E], ref: str, kind: str) -> E:
    """Remove and return the entity *ref* names."""
    entity = find(items, ref, kind)
    del items[entity.id]
    return entity


def revised[M: BaseModel](model: M, changes: Mapping[str, Any]) -> M:
    """A validated copy of *model* with *changes*; the original stays untouched."""
    data = model.model_dump()
    data.update(changes)
    try:
        return type(model).model_validate(data)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(map(str, error['loc']))}: {error['msg']}" for error in exc.errors()
        )
        raise InvalidChangeError(f"Invalid change: {problems}.") from exc


def update[E: Named](
    items: MutableMapping[str, E],
    ref: str,
    kind: str,
    changes: Mapping[str, Any],
    *,
    name_field: str = "name",
) -> E:
    """Apply *changes* to the entity *ref* names, keeping names unique."""
    entity = find(items, ref, kind)
    new_name = changes.get(name_field)
    if new_name is not None:
        ensure_name_free(items, new_name, kind, exclude_id=entity.id)
    updated = cast(E, revised(cast(BaseModel, entity), changes))
    items[entity.id] = updated
    return updated
