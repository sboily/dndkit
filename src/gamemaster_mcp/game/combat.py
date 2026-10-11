"""The initiative order: whose turn it is, by position rather than by name.

Turns are tracked by index, so three goblins each get their turn; same-named
combatants are numbered ("Goblin 1", "Goblin 2") so they can be told apart
aloud. Combatants who fall or flee move to ``defeated``, which the end of the
combat turns into an XP total.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from gamemaster_mcp.errors import InvalidChangeError, NotFoundError
from gamemaster_mcp.game import registry
from gamemaster_mcp.game.combatants import number_duplicates, unique_name
from gamemaster_mcp.models import Combatant, GameState


@dataclass(frozen=True)
class CombatSummary:
    """What a finished combat leaves: its length and who was overcome."""

    rounds: int
    defeated: list[Combatant]
    xp: int


def start(
    state: GameState, combatants: Sequence[Combatant], encounter_id: str | None = None
) -> Combatant:
    """Sort by initiative (ties keep the given order) and open round 1."""
    if state.in_combat:
        raise InvalidChangeError("A combat is already running. Use add_combatant or end_combat.")
    if not combatants:
        raise InvalidChangeError("A combat needs at least one participant.")
    ordered = sorted(combatants, key=lambda c: c.initiative, reverse=True)
    state.initiative_order = number_duplicates(ordered)
    state.in_combat = True
    state.turn_index = 0
    state.combat_round = 1
    state.defeated = []
    state.encounter_id = encounter_id
    return state.initiative_order[0]


def add(state: GameState, combatant: Combatant) -> Combatant:
    """Insert a newcomer by initiative without changing whose turn it is."""
    _require_combat(state)
    if combatant.character_id and any(
        c.character_id == combatant.character_id for c in state.initiative_order
    ):
        raise InvalidChangeError(f"{combatant.name} is already in the fight.")
    if combatant.character_id is None:
        name = unique_name(state.initiative_order, combatant.name)
        combatant = combatant.model_copy(update={"name": name})
    order = state.initiative_order
    position = next(
        (i for i, c in enumerate(order) if combatant.initiative > c.initiative), len(order)
    )
    state.initiative_order = [*order[:position], combatant, *order[position:]]
    if position <= state.turn_index:
        state.turn_index += 1
    return combatant


def next_turn(state: GameState) -> Combatant:
    """Advance one turn; passing the last combatant starts a new round."""
    _require_combat(state)
    state.turn_index += 1
    if state.turn_index >= len(state.initiative_order):
        state.turn_index = 0
        state.combat_round += 1
    return state.initiative_order[state.turn_index]


def find(state: GameState, name: str) -> Combatant:
    """The combatant *name* names (case and accents ignored)."""
    _require_combat(state)
    wanted = registry.normalize(name)
    for combatant in state.initiative_order:
        if registry.normalize(combatant.name) == wanted:
            return combatant
    listed = ", ".join(c.name for c in state.initiative_order)
    raise NotFoundError(f"No combatant named '{name}'. In the fight: {listed}.")


def remove(state: GameState, name: str) -> tuple[Combatant, Combatant | None]:
    """Take a fallen or fled combatant out; returns it and whoever acts now.

    Removing the last combatant ends the combat and returns None as the second value.
    """
    removed = find(state, name)
    index = next(i for i, c in enumerate(state.initiative_order) if c is removed)
    state.initiative_order = [c for c in state.initiative_order if c is not removed]
    if removed.character_id is None:
        state.defeated = [*state.defeated, removed]
    if not state.initiative_order:
        state.in_combat = False
        return removed, None
    if index < state.turn_index:
        state.turn_index -= 1
    elif state.turn_index >= len(state.initiative_order):
        state.turn_index = 0
        state.combat_round += 1
    return removed, state.initiative_order[state.turn_index]


def end(state: GameState) -> CombatSummary:
    """Close the combat; the summary lists who was overcome and their total XP."""
    if not state.in_combat and not state.defeated:
        raise InvalidChangeError("No combat is running.")
    summary = CombatSummary(
        rounds=state.combat_round,
        defeated=list(state.defeated),
        xp=sum(c.xp for c in state.defeated),
    )
    state.in_combat = False
    state.initiative_order = []
    state.turn_index = 0
    state.combat_round = 0
    state.defeated = []
    state.encounter_id = None
    return summary


def _require_combat(state: GameState) -> None:
    if not state.in_combat or not state.initiative_order:
        raise InvalidChangeError("No combat is running. Start one with start_combat.")
