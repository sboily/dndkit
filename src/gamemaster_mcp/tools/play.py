"""Tools used at the table: game state, hit points and conditions."""

from collections.abc import Callable
from typing import Annotated, Literal

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from pydantic import Field

from gamemaster_mcp.errors import InvalidChangeError
from gamemaster_mcp.game import effects
from gamemaster_mcp.models import now
from gamemaster_mcp.storage import CampaignStore
from gamemaster_mcp.tools import render
from gamemaster_mcp.tools.apps import PARTY_APP, app_meta
from gamemaster_mcp.tools.deps import READ_ONLY, get_store, provided

Targets = Annotated[
    list[str], Field(min_length=1, description="Characters or combatants, e.g. 'Goblin 2'")
]
Condition = Literal[
    "blinded", "charmed", "deafened", "frightened", "grappled", "incapacitated", "invisible",
    "paralyzed", "petrified", "poisoned", "prone", "restrained", "stunned", "unconscious",
]  # fmt: skip


@tool(annotations=READ_ONLY, meta=app_meta(PARTY_APP))
def get_game_state(store: CampaignStore = Depends(get_store)) -> str:
    """Where the party is: session, location, date, funds, party HP, quests, combat."""
    with store.reading() as campaign:
        return render.game_state(campaign, store.opened_at)


@tool
def update_game_state(
    current_location: Annotated[str | None, Field(description="Party's location")] = None,
    current_session: Annotated[int | None, Field(ge=1, description="Session number")] = None,
    current_date_in_game: Annotated[str | None, Field(description="In-game date")] = None,
    party_funds: Annotated[str | None, Field(description="Shared funds, e.g. '120 gp'")] = None,
    notes: Annotated[str | None, Field(description="Current situation, replaces notes")] = None,
    store: CampaignStore = Depends(get_store),
) -> str:
    """Record where the party is, the date, the session, funds or the situation."""
    changes = provided(
        current_location=current_location,
        current_session=current_session,
        current_date_in_game=current_date_in_game,
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
def change_hit_points(
    names: Targets,
    amount: Annotated[int, Field(description="Negative for damage, positive for healing")],
    temporary: Annotated[
        bool, Field(description="Grant temporary HP instead (they don't stack)")
    ] = False,
    store: CampaignStore = Depends(get_store),
) -> str:
    """Damage or heal characters and monsters. Temporary HP absorb damage first; a monster
    at 0 HP leaves the fight; a character at 0 HP falls unconscious."""
    if amount == 0:
        raise InvalidChangeError("The amount must not be 0.")
    with store.transaction() as campaign:
        if temporary:
            if amount < 0:
                raise InvalidChangeError(
                    "Temporary hit points are granted with a positive amount."
                )
            return "\n".join(effects.grant_temporary_hp(campaign, names, amount))
        return "\n".join(effects.change_hit_points(campaign, names, amount))


@tool
def set_condition(
    names: Targets,
    condition: Annotated[Condition, Field(description="5e condition")],
    active: Annotated[bool, Field(description="false to remove it")] = True,
    rounds: Annotated[
        int | None, Field(ge=1, le=100, description="Ends after its Nth turn (1 minute: 10)")
    ] = None,
    store: CampaignStore = Depends(get_store),
) -> str:
    """Add or remove a condition (poisoned, prone...) on characters or monsters. With
    rounds, next_turn ends it at the end of the target's turn that many turns on."""
    with store.transaction() as campaign:
        return "\n".join(effects.set_condition(campaign, names, condition, active, rounds))


@tool
def set_concentration(
    name: Annotated[str, Field(min_length=1, description="Character or monster")],
    spell: Annotated[str | None, Field(description="The spell held; omit to end it")] = None,
    store: CampaignStore = Depends(get_store),
) -> str:
    """Concentrate on a spell (ending any other), or stop. Damage then asks for the
    Constitution save; 0 HP or incapacitation ends it."""
    with store.transaction() as campaign:
        return effects.set_concentration(campaign, name, spell)


TOOLS: list[Callable[..., str]] = [
    get_game_state,
    update_game_state,
    change_hit_points,
    set_condition,
    set_concentration,
]
