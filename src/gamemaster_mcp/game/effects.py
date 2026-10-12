"""Hit points and conditions for anyone at the table: characters or combatants.

A whole name is looked up in the running fight first, then among the party;
only then a part of a name, if it points to one target alone. A combatant
linked to a character is changed on the character's sheet; any other
combatant keeps its own hit points and conditions, and leaves the initiative
order when it drops to 0 HP. Each change first brings the fight up
to date (``combatants.refresh``): a sheet created or a stat block saved after
the fight began takes effect at once.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from gamemaster_mcp.errors import InvalidChangeError, NotFoundError
from gamemaster_mcp.game import characters, combat, combatants, concentration, registry, rules
from gamemaster_mcp.game.concentration import INCAPACITATING
from gamemaster_mcp.models import CONDITIONS, Campaign, Character, Combatant, now


@dataclass(frozen=True)
class Target:
    """One resolved name: a party character, or a combatant with its own stats."""

    name: str
    character: Character | None = None
    combatant: Combatant | None = None


def resolve(campaign: Campaign, refs: Sequence[str]) -> list[Target]:
    """Every target in *refs*, once each, or one error naming all the unknown ones."""
    state = campaign.game_state
    fighters = state.initiative_order if state.in_combat else []
    targets: list[Target] = []
    missing: list[str] = []
    for ref in refs:
        target = _target(campaign, fighters, ref)
        if target is None:
            missing.append(ref)
        elif all(t.name != target.name for t in targets):
            targets.append(target)
    if missing:
        known = [c.name for c in fighters] + [c.name for c in campaign.characters.values()]
        unknown = ", ".join(f"'{ref}'" for ref in missing)
        raise NotFoundError(f"Unknown: {unknown}. Known: {', '.join(sorted(set(known)))}.")
    return targets


def _target(campaign: Campaign, fighters: Sequence[Combatant], ref: str) -> Target | None:
    """A whole name, a fighter's then a character's; else the only one a part names.
    "Thorn" is the character Thorn, not the "Thornback Boar"."""
    wanted = registry.normalize(ref)
    fighter = next((c for c in fighters if registry.normalize(c.name) == wanted), None)
    if fighter is not None:
        return _fighting(campaign, fighter)
    character = registry.find_exact(campaign.characters, ref)
    if character is not None:
        return Target(character.name, character=character)
    in_fight = registry.partial_matches(fighters, ref)
    linked = {c.character_id for c in in_fight}
    sheets = registry.partial_matches(campaign.characters.values(), ref)
    sheets = [c for c in sheets if c.id not in linked]
    if len(in_fight) + len(sheets) != 1:
        return None
    return _fighting(campaign, in_fight[0]) if in_fight else Target(sheets[0].name, sheets[0])


def _fighting(campaign: Campaign, fighter: Combatant) -> Target | None:
    """A fighter as a target: its sheet when it is a party character."""
    if fighter.character_id is None:
        return Target(fighter.name, combatant=fighter)
    character = campaign.characters.get(fighter.character_id)
    return Target(character.name, character=character) if character else None


def change_hit_points(campaign: Campaign, refs: Sequence[str], amount: int) -> list[str]:
    """Damage (negative) or heal (positive) each target; one line per target."""
    lines = combatants.refresh(campaign)
    for target in resolve(campaign, refs):
        holder: Character | Combatant
        if target.character is not None:
            holder = target.character
            lines.append(characters.change_hp(holder, amount))
            down = holder.hit_points_current == 0
        elif target.combatant is not None:
            holder = target.combatant
            lines.append(_change_combatant_hp(campaign, holder, amount))
            down = not holder.hit_points
        else:
            continue
        if amount < 0 and (held := concentration.after_damage(holder, target.name, -amount, down)):
            lines.append(held)
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
        if (
            active
            and condition in INCAPACITATING
            and (lost := concentration.lose(holder, target.name))
        ):
            lines.append(lost)
    return lines


def set_concentration(campaign: Campaign, ref: str, spell: str | None) -> str:
    """Start or stop concentrating, for a character or a combatant."""
    combatants.refresh(campaign)
    (target,) = resolve(campaign, [ref])
    holder = target.character or target.combatant
    if holder is None:
        raise NotFoundError(f"Unknown: '{ref}'.")
    return concentration.concentrate(holder, target.name, spell)
