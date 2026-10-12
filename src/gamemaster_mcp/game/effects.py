"""Hit points and conditions for anyone at the table: characters or combatants.

A name is looked up in the running fight first, then among the party. A
combatant linked to a character is changed on the character's sheet; any
other combatant keeps its own hit points and conditions, and leaves the
initiative order when it drops to 0 HP. Each change first brings the fight up
to date (``combatants.refresh``): a sheet created or a stat block saved after
the fight began takes effect at once.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from gamemaster_mcp.errors import InvalidChangeError, NotFoundError
from gamemaster_mcp.game import characters, combat, combatants, registry, rules
from gamemaster_mcp.models import CONDITIONS, Campaign, Character, Combatant, now


@dataclass(frozen=True)
class Target:
    """One resolved name: a party character, or a combatant with its own stats."""

    name: str
    character: Character | None = None
    combatant: Combatant | None = None


def resolve(campaign: Campaign, refs: Sequence[str]) -> list[Target]:
    """Every target in *refs*, or one error naming all the unknown ones."""
    state = campaign.game_state
    fighters = state.initiative_order if state.in_combat else []
    targets: list[Target] = []
    missing: list[str] = []
    for ref in refs:
        fighter = combat.find_optional(state, ref) if fighters else None
        if fighter is not None and fighter.character_id is None:
            targets.append(Target(fighter.name, combatant=fighter))
            continue
        ref_or_id = fighter.character_id if fighter and fighter.character_id else ref
        character = registry.find_optional(campaign.characters, ref_or_id)
        if character is None:
            missing.append(ref)
        else:
            targets.append(Target(character.name, character=character))
    if missing:
        known = [c.name for c in fighters] + [c.name for c in campaign.characters.values()]
        unknown = ", ".join(f"'{ref}'" for ref in missing)
        raise NotFoundError(f"Unknown: {unknown}. Known: {', '.join(sorted(set(known)))}.")
    return targets


def change_hit_points(campaign: Campaign, refs: Sequence[str], amount: int) -> list[str]:
    """Damage (negative) or heal (positive) each target; one line per target."""
    lines = combatants.refresh(campaign)
    for target in resolve(campaign, refs):
        if target.character is not None:
            lines.append(characters.change_hp(target.character, amount))
        elif target.combatant is not None:
            lines.append(_change_combatant_hp(campaign, target.combatant, amount))
    return lines


def _change_combatant_hp(campaign: Campaign, combatant: Combatant, amount: int) -> str:
    if combatant.hit_points is None:
        raise InvalidChangeError(
            f"{combatant.name}'s hit points are not tracked: save its stat block with "
            "save_monster (it then fights with it), then change its hit points again."
        )
    maximum = combatant.hit_points_max or combatant.hit_points
    hp = rules.apply_hp_change(combatant.hit_points, maximum, 0, amount)
    combatant.hit_points = hp.current
    if hp.current > 0:
        return f"{combatant.name}: HP {hp.current}/{maximum}"
    _, acting = combat.remove(campaign.game_state, combatant.name)
    after = f" {acting.name} acts now." if acting else " No one is left: call end_combat."
    return f"{combatant.name} drops to 0 HP and leaves the fight.{after}"


def grant_temporary_hp(campaign: Campaign, refs: Sequence[str], amount: int) -> list[str]:
    """Temporary hit points don't stack: each character keeps the higher value."""
    lines = combatants.refresh(campaign)
    for target in resolve(campaign, refs):
        if target.character is None:
            raise InvalidChangeError("Temporary hit points are tracked for characters only.")
        character = target.character
        character.temporary_hit_points = max(character.temporary_hit_points, amount)
        character.updated_at = now()
        lines.append(f"{character.name}: {character.temporary_hit_points} temporary HP")
    return lines


def set_condition(
    campaign: Campaign, refs: Sequence[str], condition: str, active: bool
) -> list[str]:
    """Add or remove one condition on each target; one line per target."""
    if condition not in CONDITIONS:
        raise InvalidChangeError(
            f"Unknown condition '{condition}'. Conditions: {', '.join(CONDITIONS)}."
        )
    lines = combatants.refresh(campaign)
    for target in resolve(campaign, refs):
        holder = target.character or target.combatant
        if holder is None:
            continue
        others = [c for c in holder.conditions if c != condition]
        holder.conditions = [*others, condition] if active else others
        listed = ", ".join(holder.conditions) or "no condition"
        lines.append(f"{target.name}: {listed}")
    return lines
