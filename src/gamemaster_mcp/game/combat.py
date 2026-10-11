"""The initiative order: whose turn it is, by position rather than by name.

Turns are tracked by index, so three goblins sharing a name each get their
turn; duplicate names are numbered ("Goblin 1", "Goblin 2") so they can be
told apart aloud.
"""

from collections import Counter
from collections.abc import Sequence

from gamemaster_mcp.errors import InvalidChangeError, NotFoundError
from gamemaster_mcp.game import registry
from gamemaster_mcp.models import Combatant, GameState


def start(state: GameState, participants: Sequence[Combatant]) -> Combatant:
    """Sort by initiative (ties keep the given order) and open round 1."""
    if state.in_combat:
        raise InvalidChangeError("A combat is already running. Call end_combat first.")
    if not participants:
        raise InvalidChangeError("A combat needs at least one participant.")
    ordered = sorted(participants, key=lambda c: c.initiative, reverse=True)
    state.initiative_order = _number_duplicates(ordered)
    state.in_combat = True
    state.turn_index = 0
    state.combat_round = 1
    return state.initiative_order[0]


def _number_duplicates(order: Sequence[Combatant]) -> list[Combatant]:
    totals = Counter(registry.normalize(c.name) for c in order)
    seen: Counter[str] = Counter()
    numbered: list[Combatant] = []
    for combatant in order:
        key = registry.normalize(combatant.name)
        if totals[key] > 1:
            seen[key] += 1
            combatant = combatant.model_copy(update={"name": f"{combatant.name} {seen[key]}"})
        numbered.append(combatant)
    return numbered


def next_turn(state: GameState) -> Combatant:
    """Advance one turn; passing the last combatant starts a new round."""
    _require_combat(state)
    state.turn_index += 1
    if state.turn_index >= len(state.initiative_order):
        state.turn_index = 0
        state.combat_round += 1
    return state.initiative_order[state.turn_index]


def remove_combatant(state: GameState, name: str) -> tuple[Combatant, Combatant | None]:
    """Take a fallen or fled combatant out; returns it and whoever acts now.

    When the last combatant leaves, the combat ends and the second value is None.
    """
    _require_combat(state)
    wanted = registry.normalize(name)
    order = state.initiative_order
    index = next((i for i, c in enumerate(order) if registry.normalize(c.name) == wanted), None)
    if index is None:
        listed = ", ".join(c.name for c in order)
        raise NotFoundError(f"No combatant named '{name}'. In the fight: {listed}.")
    removed = order[index]
    state.initiative_order = order[:index] + order[index + 1 :]
    if not state.initiative_order:
        end(state)
        return removed, None
    if index < state.turn_index:
        state.turn_index -= 1
    elif state.turn_index >= len(state.initiative_order):
        state.turn_index = 0
        state.combat_round += 1
    return removed, state.initiative_order[state.turn_index]


def end(state: GameState) -> int:
    """Close the combat; returns how many rounds it lasted."""
    rounds = state.combat_round
    state.in_combat = False
    state.initiative_order = []
    state.turn_index = 0
    state.combat_round = 0
    return rounds


def _require_combat(state: GameState) -> None:
    if not state.in_combat or not state.initiative_order:
        raise InvalidChangeError("No combat is running. Start one with start_combat.")
