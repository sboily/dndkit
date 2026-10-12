"""Who sits at the table tonight, and which character each plays.

A player is a person, named as the voice client names their voice: roomkit-ui
opens each spoken turn with the speaker's name. A character's
``player_name`` ties it to its player. The roll call (``seat``) says who is
present; until there is one, the whole party counts as present.
"""

from dndkit.errors import InvalidChangeError, NotFoundError
from dndkit.game import characters
from dndkit.models import Campaign, Character, now
from dndkit.text import normalize


def same_person(a: str | None, b: str | None) -> bool:
    """Two spellings of one name (case and accents aside)."""
    return a is not None and b is not None and normalize(a) == normalize(b)


def characters_of(campaign: Campaign, player: str) -> list[Character]:
    """The characters *player* plays, by name."""
    played = [c for c in campaign.characters.values() if same_person(c.player_name, player)]
    return sorted(played, key=lambda c: c.name)


def is_present(campaign: Campaign, character: Character) -> bool:
    """Whether *character*'s player answered the roll call; True when there was none."""
    present = campaign.game_state.players_present
    return not present or any(same_person(character.player_name, p) for p in present)


def present_characters(campaign: Campaign) -> list[Character]:
    """The characters at the table: the whole party until a roll call."""
    return [c for c in campaign.characters.values() if is_present(campaign, c)]


def seat(campaign: Campaign, player: str, character_ref: str | None) -> str | None:
    """Seat *player*, with the character they play if given.

    Returns a note when the character changes hands, for the model to say.
    """
    name = " ".join(player.split())
    if not name:
        raise InvalidChangeError("A player needs a name.")
    note = None
    if character_ref:
        character = characters.find(campaign, character_ref)
        previous = character.player_name
        if previous and not same_person(previous, name):
            note = f"{character.name} was played by {previous}, now by {name}."
        character.player_name = name
        character.updated_at = now()
    state = campaign.game_state
    if not any(same_person(p, name) for p in state.players_present):
        state.players_present = [*state.players_present, name]
    return note


def leave(campaign: Campaign, player: str) -> None:
    """Take *player* off the table; their characters stay in the party."""
    state = campaign.game_state
    seated = next((p for p in state.players_present if same_person(p, player)), None)
    if seated is None:
        at_table = ", ".join(state.players_present) or "nobody"
        raise NotFoundError(f"{player} is not at the table. At the table: {at_table}.")
    state.players_present = [p for p in state.players_present if p != seated]


def clear(campaign: Campaign) -> None:
    """Forget the last roll call: a new session starts."""
    campaign.game_state.players_present = []
