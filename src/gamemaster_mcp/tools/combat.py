"""Combat tools: the initiative order, turns, newcomers and the end of the fight."""

from collections.abc import Callable
from typing import Annotated, Literal

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from pydantic import Field

from gamemaster_mcp.errors import InvalidChangeError
from gamemaster_mcp.game import battlefield, bestiary, combat, combatants
from gamemaster_mcp.game.dice import DiceLog
from gamemaster_mcp.models import Participant
from gamemaster_mcp.storage import CampaignStore
from gamemaster_mcp.tools import render_combat
from gamemaster_mcp.tools.apps import COMBAT_APP, app_meta
from gamemaster_mcp.tools.deps import get_dice_log, get_store


@tool(meta=app_meta(COMBAT_APP))
def start_combat(
    participants: Annotated[
        list[Participant] | None,
        Field(description="Who fights, with initiative; the party rolls if left out"),
    ] = None,
    encounter: Annotated[
        str | None, Field(description="Planned encounter: its monsters join, initiative rolled")
    ] = None,
    store: CampaignStore = Depends(get_store),
    log: DiceLog = Depends(get_dice_log),
) -> str:
    """Start a combat. Party characters use their sheet; bestiary monsters get their stats;
    same-named foes become 'Goblin 1', 'Goblin 2'."""
    with store.transaction() as campaign:
        fighters = [combatants.build(campaign, p) for p in participants or []]
        planned = bestiary.find_encounter(campaign, encounter) if encounter else None
        state = campaign.game_state
        if planned is not None:
            fighters += combatants.from_encounter(campaign, planned)
            planned.status = "running"
            if planned.battlefield is not None:
                state.battlefield = planned.battlefield.model_copy(deep=True)
        if not fighters:
            raise InvalidChangeError("Give participants, an encounter, or both.")
        party = any(f.character_id for f in fighters)
        rolled = [] if party else combatants.party_at_the_table(campaign)
        fighters += [fighter for fighter, _ in rolled]
        first = combat.start(state, fighters, planned.id if planned else None)
        if state.battlefield is not None:
            battlefield.settle(state)
            battlefield.place_the_rest(state)
        order = render_combat.initiative(campaign)
    for _, result in rolled:
        log.record(result)
    rolls = ", ".join(f"{c.name} {r.total}" for c, r in rolled)
    note = f"Initiative rolled for the party: {rolls}.\n" if rolls else ""
    return f"Combat started. {first.name} acts first.\n{note}{order}"


@tool
def add_combatant(
    participant: Annotated[Participant, Field(description="The newcomer and its initiative")],
    store: CampaignStore = Depends(get_store),
) -> str:
    """Bring someone into the running fight (reinforcements, a late arrival)."""
    with store.transaction() as campaign:
        added = combat.add(campaign.game_state, combatants.build(campaign, participant))
        battlefield.place_the_rest(campaign.game_state)
        order = render_combat.initiative(campaign)
    return f"{added.name} joins the fight.\n{order}"


@tool
def next_turn(store: CampaignStore = Depends(get_store)) -> str:
    """End the current turn and give the next combatant theirs."""
    with store.transaction() as campaign:
        state = campaign.game_state
        caught_up = combatants.refresh(campaign)
        current = combat.next_turn(state)
        prefix = f"Round {state.combat_round} begins. " if state.turn_index == 0 else ""
        line = render_combat.combatant_line(campaign, current)
    return "\n".join([*caught_up, f"{prefix}{current.name}'s turn: {line}"])


@tool
def remove_combatant(
    name: Annotated[str, Field(min_length=1, description="Combatant name, e.g. 'Goblin 2'")],
    reason: Annotated[
        Literal["defeated", "fled", "withdrawn"],
        Field(description="withdrawn: a mistake or change of plan, no XP"),
    ] = "defeated",
    store: CampaignStore = Depends(get_store),
) -> str:
    """Take a combatant out of the fight and off the battle map. Defeated or fled foes
    count for XP; a withdrawn one is as if it never joined."""
    with store.transaction() as campaign:
        removed, acting = combat.remove(campaign.game_state, name, overcome=reason != "withdrawn")
    gone = (
        f"{removed.name} withdrawn: as if it never joined, no XP."
        if reason == "withdrawn"
        else f"{removed.name} removed ({reason})."
    )
    if acting is None:
        return f"{gone} No one is left: call end_combat."
    return f"{gone} Current turn: {acting.name}."


@tool
def use_legendary(
    name: Annotated[str, Field(min_length=1, description="The legendary creature")],
    resistance: Annotated[bool, Field(description="Turn a failed save into a success")] = False,
    cost: Annotated[int, Field(ge=1, le=3, description="Actions the option costs")] = 1,
    store: CampaignStore = Depends(get_store),
) -> str:
    """Spend a legendary action (at the end of another creature's turn) or resistance."""
    with store.transaction() as campaign:
        creature = combat.use_legendary(campaign.game_state, name, resistance, cost)
    if resistance:
        return (
            f"{creature.name} succeeds instead; "
            f"{creature.legendary_resistances_left} legendary resistance(s) left."
        )
    return (
        f"{creature.name} takes a legendary action; "
        f"{creature.legendary_actions_left} left until its turn."
    )


@tool
def end_combat(store: CampaignStore = Depends(get_store)) -> str:
    """End the combat: says who was overcome and the XP they are worth."""
    with store.transaction() as campaign:
        encounter_id = campaign.game_state.encounter_id
        summary = combat.end(campaign.game_state)
        if encounter_id and encounter_id in campaign.encounters:
            campaign.encounters[encounter_id].status = "done"
    defeated = ", ".join(c.name for c in summary.defeated) or "no one"
    award = f" Award it with award_experience ({summary.xp} XP)." if summary.xp else ""
    return f"Combat over after {summary.rounds} round(s). Overcome: {defeated}.{award}"


TOOLS: list[Callable[..., str]] = [
    start_combat,
    add_combatant,
    next_turn,
    remove_combatant,
    use_legendary,
    end_combat,
]
