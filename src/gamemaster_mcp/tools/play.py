"""Tools used at the table: game state and combat turns."""

from collections.abc import Callable
from typing import Annotated

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from pydantic import Field

from gamemaster_mcp.errors import InvalidChangeError
from gamemaster_mcp.game import combat
from gamemaster_mcp.models import Combatant, now
from gamemaster_mcp.storage import CampaignStore
from gamemaster_mcp.tools import render
from gamemaster_mcp.tools.deps import READ_ONLY, get_store, provided


@tool(annotations=READ_ONLY)
def get_game_state(store: CampaignStore = Depends(get_store)) -> str:
    """Where the party is: session, location, date, funds, active quests, combat."""
    with store.reading() as campaign:
        return render.game_state(campaign)


@tool
def update_game_state(
    current_location: Annotated[str | None, Field(description="Party's location")] = None,
    current_session: Annotated[int | None, Field(ge=1, description="Session number")] = None,
    current_date_in_game: Annotated[str | None, Field(description="In-game date")] = None,
    party_level: Annotated[int | None, Field(ge=1, le=20, description="Party level")] = None,
    party_funds: Annotated[str | None, Field(description="Shared funds, e.g. '120 gp'")] = None,
    notes: Annotated[str | None, Field(description="Current situation, replaces notes")] = None,
    store: CampaignStore = Depends(get_store),
) -> str:
    """Record where the party is, the date, the session, party level, funds or situation."""
    changes = provided(
        current_location=current_location,
        current_session=current_session,
        current_date_in_game=current_date_in_game,
        party_level=party_level,
        party_funds=party_funds,
        notes=notes,
    )
    if not changes:
        raise InvalidChangeError("Nothing to change: give at least one field.")
    with store.transaction() as campaign:
        state = campaign.game_state
        for field, value in changes.items():
            setattr(state, field, value)
        state.updated_at = now()
    return f"Game state updated: {', '.join(changes)}."


@tool
def start_combat(
    participants: Annotated[
        list[Combatant],
        Field(min_length=1, description="Everyone in the fight with their initiative roll"),
    ],
    store: CampaignStore = Depends(get_store),
) -> str:
    """Start a combat: sorts by initiative; same-named foes become 'Goblin 1', 'Goblin 2'."""
    with store.transaction() as campaign:
        first = combat.start(campaign.game_state, participants)
        order = render.initiative(campaign.game_state)
    return f"Combat started. {first.name} acts first.\n{order}"


@tool
def next_turn(store: CampaignStore = Depends(get_store)) -> str:
    """End the current turn and give the next combatant theirs."""
    with store.transaction() as campaign:
        state = campaign.game_state
        current = combat.next_turn(state)
        new_round = state.turn_index == 0
    prefix = f"Round {state.combat_round} begins. " if new_round else ""
    return f"{prefix}{current.name}'s turn (initiative {current.initiative})."


@tool
def remove_combatant(
    name: Annotated[str, Field(min_length=1, description="Combatant name, e.g. 'Goblin 2'")],
    store: CampaignStore = Depends(get_store),
) -> str:
    """Take a defeated or fleeing combatant out of the initiative order."""
    with store.transaction() as campaign:
        removed, acting = combat.remove_combatant(campaign.game_state, name)
    if acting is None:
        return f"{removed.name} removed. No one is left: combat over."
    return f"{removed.name} removed. Current turn: {acting.name}."


@tool
def end_combat(store: CampaignStore = Depends(get_store)) -> str:
    """End the combat and clear the initiative order."""
    with store.transaction() as campaign:
        if not campaign.game_state.in_combat:
            raise InvalidChangeError("No combat is running.")
        rounds = combat.end(campaign.game_state)
    return f"Combat over after {rounds} round(s)."


TOOLS: list[Callable[..., str]] = [
    get_game_state,
    update_game_state,
    start_combat,
    next_turn,
    remove_combatant,
    end_combat,
]
