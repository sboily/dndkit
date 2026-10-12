"""Character tools: create, read and change player characters."""

from collections.abc import Callable
from typing import Annotated

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from pydantic import Field

from dndkit.errors import InvalidChangeError
from dndkit.game import characters, combatants, rules
from dndkit.models import AbilityScore, Character, CharacterClass, Race
from dndkit.storage import CampaignStore
from dndkit.tools import render
from dndkit.tools.apps import CHARACTER_APP, app_meta
from dndkit.tools.deps import READ_ONLY, NameOrId, get_store, provided

Score = Annotated[int, Field(ge=1, le=30, description="Ability score (1-30)")]
NewScore = Annotated[int | None, Field(ge=1, le=30, description="New score (1-30)")]
Text = Annotated[str | None, Field(description="New value")]


@tool
def create_character(
    name: Annotated[str, Field(min_length=1, description="Character name")],
    character_class: Annotated[str, Field(min_length=1, description="Class, e.g. Wizard")],
    race: Annotated[str, Field(min_length=1, description="Race or species, e.g. Elf")],
    class_level: Annotated[int, Field(ge=1, le=20, description="Class level")] = 1,
    hit_points_max: Annotated[
        int | None, Field(ge=1, description="Max HP; from class and CON if omitted")
    ] = None,
    armor_class: Annotated[
        int | None, Field(ge=0, description="AC; 10 + DEX (no armor) if omitted")
    ] = None,
    speed: Annotated[int | None, Field(ge=0, description="Feet; from race if omitted")] = None,
    player_name: Annotated[str | None, Field(description="Player controlling it")] = None,
    description: Annotated[str | None, Field(description="Appearance and demeanor")] = None,
    bio: Annotated[str | None, Field(description="Backstory and motivations")] = None,
    background: Annotated[str | None, Field(description="Background, e.g. Sage")] = None,
    alignment: Annotated[str | None, Field(description="Alignment")] = None,
    strength: Score = 10,
    dexterity: Score = 10,
    constitution: Score = 10,
    intelligence: Score = 10,
    wisdom: Score = 10,
    charisma: Score = 10,
    store: CampaignStore = Depends(get_store),
) -> str:
    """Create a player character at full hit points. The name must be new."""
    scores = dict(
        strength=strength,
        dexterity=dexterity,
        constitution=constitution,
        intelligence=intelligence,
        wisdom=wisdom,
        charisma=charisma,
    )
    mods = {key: (value - 10) // 2 for key, value in scores.items()}
    if hit_points_max is None:
        hit_points_max = rules.starting_hit_points(
            character_class, class_level, mods["constitution"]
        )
    if armor_class is None:
        armor_class = 10 + mods["dexterity"]
    character = Character(
        name=name.strip(),
        player_name=player_name,
        character_class=CharacterClass(name=character_class, level=class_level),
        race=Race(name=race),
        background=background,
        alignment=alignment,
        description=description,
        bio=bio,
        armor_class=armor_class,
        speed=speed if speed is not None else rules.base_speed(race),
        hit_points_max=hit_points_max,
        hit_points_current=hit_points_max,
        abilities={k: AbilityScore(score=v) for k, v in scores.items()},
    )
    with store.transaction() as campaign:
        characters.create(campaign, character)
        caught_up = combatants.refresh(campaign)  # a fighter of that name joins its sheet
    casting = render.spellcasting_line(character)
    return " ".join([f"Created {render.character_line(character)}.", casting, *caught_up]).strip()


@tool(annotations=READ_ONLY, meta=app_meta(CHARACTER_APP))
def get_character(
    name_or_id: Annotated[
        str | None, Field(description="Name or ID; omit for whose turn it is")
    ] = None,
    store: CampaignStore = Depends(get_store),
) -> str:
    """Full character sheet: abilities, hit points, spell attack and DC, spells, inventory."""
    with store.reading() as campaign:
        return render.character_sheet(characters.pick(campaign, name_or_id))


@tool(annotations=READ_ONLY)
def list_characters(store: CampaignStore = Depends(get_store)) -> str:
    """List the party's characters with level, class and hit points."""
    with store.reading() as campaign:
        party = sorted(campaign.characters.values(), key=lambda c: c.name)
        if not party:
            return "No characters yet."
        lines = [f"- {render.character_line(c)}" for c in party]
        return "\n".join(["Characters:", *lines, render.table(campaign, store.opened_at)])


@tool
def update_character(
    name_or_id: NameOrId,
    name: Annotated[str | None, Field(description="New name")] = None,
    player_name: Text = None,
    description: Text = None,
    bio: Text = None,
    background: Text = None,
    alignment: Text = None,
    class_level: Annotated[
        int | None, Field(ge=1, le=20, description="Corrected level; level_up gains one")
    ] = None,
    hit_points_current: Annotated[int | None, Field(ge=0, description="Current HP")] = None,
    hit_points_max: Annotated[int | None, Field(ge=1, description="Maximum HP")] = None,
    temporary_hit_points: Annotated[int | None, Field(ge=0, description="Temporary HP")] = None,
    armor_class: Annotated[int | None, Field(ge=0, description="Armor class")] = None,
    speed: Annotated[int | None, Field(ge=0, description="Walking speed, feet")] = None,
    inspiration: Annotated[bool | None, Field(description="Has inspiration")] = None,
    exhaustion: Annotated[int | None, Field(ge=0, le=6, description="Exhaustion level")] = None,
    notes: Text = None,
    skills: Annotated[list[str] | None, Field(description="Proficient skills")] = None,
    expertise: Annotated[
        list[str] | None, Field(description="Skills with double proficiency")
    ] = None,
    saving_throws: Annotated[list[str] | None, Field(description="Proficient saves: DEX")] = None,
    languages: Annotated[list[str] | None, Field(description="Languages spoken")] = None,
    features: Annotated[list[str] | None, Field(description="Features, traits, feats")] = None,
    strength: NewScore = None,
    dexterity: NewScore = None,
    constitution: NewScore = None,
    intelligence: NewScore = None,
    wisdom: NewScore = None,
    charisma: NewScore = None,
    store: CampaignStore = Depends(get_store),
) -> str:
    """Set character sheet values (absolute; a list replaces the old one). For damage or
    healing use change_hit_points. Skills and saves take English or French names."""
    changes = provided(
        name=name,
        player_name=player_name,
        description=description,
        bio=bio,
        background=background,
        alignment=alignment,
        class_level=class_level,
        hit_points_current=hit_points_current,
        hit_points_max=hit_points_max,
        temporary_hit_points=temporary_hit_points,
        armor_class=armor_class,
        speed=speed,
        inspiration=inspiration,
        exhaustion=exhaustion,
        notes=notes,
        skill_proficiencies=skills,
        skill_expertise=expertise,
        saving_throw_proficiencies=saving_throws,
        languages=languages,
        features_and_traits=features,
    )
    abilities = provided(
        strength=strength,
        dexterity=dexterity,
        constitution=constitution,
        intelligence=intelligence,
        wisdom=wisdom,
        charisma=charisma,
    )
    if not changes and not abilities:
        raise InvalidChangeError("Nothing to change: give at least one field.")
    with store.transaction() as campaign:
        character = characters.update(campaign, name_or_id, changes, abilities)
    return f"Updated {', '.join([*changes, *abilities])}. Now: {render.character_line(character)}."


TOOLS: list[Callable[..., str]] = [
    create_character,
    get_character,
    list_characters,
    update_character,
]
