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
from gamemaster_mcp.models import Combatant, CombatRecord, GameState


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
    if state.battlefield is not None:  # the last area of effect is spent
        state.battlefield.area, state.battlefield.area_label = [], None
    return _begin_turn(state.initiative_order[state.turn_index])


def find(state: GameState, name: str) -> Combatant:
    """The combatant *name* names (case and accents ignored), or the only one whose
    name holds it ("gardien" for "Gardien de Magma"), as spoken names go."""
    _require_combat(state)
    found = find_optional(state, name)
    if found is None:
        listed = ", ".join(c.name for c in state.initiative_order)
        raise NotFoundError(f"No combatant named '{name}'. In the fight: {listed}.")
    return found


def find_optional(state: GameState, name: str) -> Combatant | None:
    """Like ``find``, or None."""
    wanted = registry.normalize(name)
    for combatant in state.initiative_order:
        if registry.normalize(combatant.name) == wanted:
            return combatant
    partial = [c for c in state.initiative_order if wanted in registry.normalize(c.name)]
    return partial[0] if len(wanted) >= 3 and len(partial) == 1 else None


def remove(
    state: GameState, name: str, overcome: bool = True
) -> tuple[Combatant, Combatant | None]:
    """Take a combatant out of the fight and off the map; returns it and whoever acts now.

    An *overcome* foe (fallen or fled) joins the defeated and counts for XP; one
    taken back (a mistake, a change of plan) leaves no trace. Removing the last
    combatant ends the combat and returns None as the second value.
    """
    removed = find(state, name)
    index = next(i for i, c in enumerate(state.initiative_order) if c is removed)
    state.initiative_order = [c for c in state.initiative_order if c is not removed]
    if overcome and removed.character_id is None:
        state.defeated = [*state.defeated, removed]
    if not state.initiative_order:
        state.in_combat = False
        return removed, None
    if index < state.turn_index:
        state.turn_index -= 1
    elif index == state.turn_index:  # the one acting left: the next one's turn starts
        if state.turn_index >= len(state.initiative_order):
            state.turn_index = 0
            state.combat_round += 1
        _begin_turn(state.initiative_order[state.turn_index])
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
    state.last_combat = CombatRecord(
        rounds=summary.rounds,
        fighters=[c.name for c in [*state.initiative_order, *state.defeated]],
        defeated=[c.name for c in summary.defeated],
        xp=summary.xp,
    )
    state.in_combat = False
    state.initiative_order = []
    state.turn_index = 0
    state.combat_round = 0
    state.defeated = []
    state.encounter_id = None
    state.battlefield = None  # the next fight lays out its own
    return summary


def _begin_turn(combatant: Combatant) -> Combatant:
    """A turn starts with the full movement, no Dash or Disengage yet, and the
    legendary actions back (MM, "Legendary Creatures")."""
    combatant.movement_used = 0
    combatant.dashed = False
    combatant.disengaged = False
    combatant.legendary_actions_left = combatant.legendary_actions
    return combatant


def use_legendary(state: GameState, name: str, resistance: bool, cost: int) -> Combatant:
    """Spend a legendary action (*cost* of them) or a legendary resistance."""
    creature = find(state, name)
    if resistance:
        if creature.legendary_resistances_left < 1:
            raise InvalidChangeError(f"{creature.name} has no legendary resistance left.")
        creature.legendary_resistances_left -= 1
        return creature
    if creature is state.current_combatant:
        raise InvalidChangeError("Legendary actions come at the end of another creature's turn.")
    if creature.legendary_actions_left < cost:
        raise InvalidChangeError(
            f"{creature.name} has {creature.legendary_actions_left} legendary action(s) left "
            "this round; they come back at the start of its turn."
        )
    creature.legendary_actions_left -= cost
    return creature


def _require_combat(state: GameState) -> None:
    if not state.in_combat or not state.initiative_order:
        raise InvalidChangeError("No combat is running. Start one with start_combat.")
