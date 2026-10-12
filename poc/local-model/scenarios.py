"""Table turns a game master hears, and what the campaign must hold afterwards.

Each scenario starts from the same campaign (``SEED``), adds its own state, then
plays one or two spoken turns. It passes when the calls it needs were made and
the campaign ends up as the rules say; the calls that failed or were not
needed are counted apart, as the price of getting there.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

Call = dict[str, Any]  # name, arguments, error, result
State = dict[str, Any]  # the views read after the turns (party, combat, sheets...)
Check = Callable[[list[Call], State], list[str]]  # what went wrong, if anything

SEED: list[tuple[str, dict[str, Any]]] = [
    (
        "create_campaign",
        {"name": "La Crypte d'Essai", "description": "Une crypte sous l'auberge."},
    ),
    (
        "create_character",
        {
            "name": "Thrain",
            "character_class": "Guerrier",
            "race": "Nain",
            "class_level": 3,
            "player_name": "Sylvain",
            "strength": 16,
            "dexterity": 12,
            "constitution": 14,
        },
    ),
    (
        "create_character",
        {
            "name": "Aria",
            "character_class": "Magicienne",
            "race": "Elfe",
            "player_name": "Marie",
            "intelligence": 16,
            "dexterity": 14,
            "constitution": 12,
        },
    ),
    ("update_character", {"name_or_id": "Thrain", "skills": ["Athlétisme", "Perception"]}),
    (
        "create_npc",
        {"name": "Mara", "occupation": "aubergiste", "description": "Une vieille femme"},
    ),
    ("create_quest", {"title": "La cloche de la crypte", "description": "Faire taire la cloche."}),
    (
        "save_monster",
        {"name": "Gobelin", "armor_class": 15, "hit_points": 7, "challenge_rating": "1/4"},
    ),
]
SEATED = (
    "seat_players",
    {
        "players": [
            {"player": "Sylvain", "character": "Thrain"},
            {"player": "Marie", "character": "Aria"},
        ],
        "start_over": True,
    },
)
FIGHT = (
    "start_combat",
    {
        "participants": [
            {"name": "Thrain", "initiative": 15},
            {"name": "Aria", "initiative": 12},
            {"name": "Gobelin", "initiative": 8},
        ]
    },
)


@dataclass(frozen=True)
class Scenario:
    name: str
    turns: list[tuple[str, str]]  # (speaker, what they say)
    check: Check
    seed: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    fresh: bool = False  # no campaign at all: SEED is not played


def called(calls: list[Call], name: str) -> list[Call]:
    """The successful calls to *name*."""
    return [c for c in calls if c["name"] == name and not c["error"]]


def needs(calls: list[Call], *names: str) -> list[str]:
    return [f"no successful {name}" for name in names if not called(calls, name)]


def mentions(call: Call, key: str, word: str) -> bool:
    return word.lower() in str(call["arguments"].get(key, "")).lower()


def fighter(state: State, name: str) -> dict[str, Any]:
    order = state["combat"]["order"]
    return next((f for f in order if f["name"].lower().startswith(name.lower())), {})


def sheet(state: State, name: str) -> dict[str, Any]:
    return state["sheets"].get(name, {})


# Each check reads the calls and the state, and says what is wrong.


def seated(calls: list[Call], state: State) -> list[str]:
    seats = {s["player"]: [c["name"] for c in s["characters"]] for s in state["seating"]["seats"]}
    wrong = (
        []
        if seats.get("Sylvain") == ["Thrain"] and seats.get("Marie") == ["Aria"]
        else [f"seating is {seats}"]
    )
    return needs(calls, "seat_players") + wrong


def asked_mara(calls: list[Call], state: State) -> list[str]:
    looked = [c for c in called(calls, "get_npc") if mentions(c, "name_or_id", "mara")]
    made = called(calls, "create_npc")
    return (["did not read Mara (get_npc)"] if not looked else []) + (
        ["created an NPC"] if made else []
    )


def attacked(calls: list[Call], state: State) -> list[str]:
    """An attack roll; a hit's damage applied with change_hit_points, to the goblin."""
    rolls = called(calls, "roll_dice")
    problems = (
        []
        if any("d20" in str(c["arguments"].get("notation")) for c in rolls)
        else ["no attack roll (d20)"]
    )
    damage = [c for c in rolls if "d20" not in str(c["arguments"].get("notation"))]
    hurt = called(calls, "change_hit_points")
    if damage and not hurt:
        problems.append("damage rolled but never applied with change_hit_points")
    if any(not any("gob" in n.lower() for n in c["arguments"].get("names", [])) for c in hurt):
        problems.append("changed the hit points of someone else than the goblin")
    if called(calls, "remove_combatant"):
        problems.append("removed the goblin by hand instead of letting its hit points decide")
    return problems


def magic_missile(calls: list[Call], state: State) -> list[str]:
    problems = needs(calls, "use_spell_slot", "change_hit_points")
    slots = sheet(state, "Aria").get("slots", [])
    if not slots or slots[0][1] != slots[0][2] - 1:
        problems.append(f"Aria's level 1 slots are {slots}")
    goblin = fighter(state, "Gobelin")
    if goblin and goblin.get("hp") == 7:
        problems.append("the goblin was not hurt")
    return problems


def turn_passed(calls: list[Call], state: State) -> list[str]:
    problems = needs(calls, "next_turn")
    if state["combat"]["round"] == 1 and fighter(state, "Thrain").get("current"):
        problems.append("still Thrain's turn")
    return problems


def short_rest(calls: list[Call], state: State) -> list[str]:
    rests = called(calls, "rest")
    problems = [] if rests else ["no successful rest"]
    if rests and not any(c["arguments"].get("hit_dice") == 2 for c in rests):
        problems.append(f"rest without hit_dice=2: {[c['arguments'] for c in rests]}")
    if sheet(state, "Thrain").get("hit_dice") != "1d10":
        problems.append(f"Thrain's hit dice are {sheet(state, 'Thrain').get('hit_dice')}")
    return problems


def picked_up(calls: list[Call], state: State) -> list[str]:
    problems = needs(calls, "add_item_to_character")
    items = [i["name"].lower() for i in sheet(state, "Aria").get("inventory", [])]
    if not any("dague" in i or "dagger" in i for i in items):
        problems.append(f"Aria carries {items}")
    return problems


def searched(calls: list[Call], state: State) -> list[str]:
    rolls = called(calls, "roll_dice")
    return (
        []
        if any("d20" in str(c["arguments"].get("notation", "")) for c in rolls)
        else ["no d20 rolled"]
    )


def charged(calls: list[Call], state: State) -> list[str]:
    """Thrain (25 ft) starts 35 ft from the goblin: as close as his speed allows, or next
    to it with a Dash."""
    problems = needs(calls, "move_token")
    tokens = (
        {t["name"]: t for t in state["combat"]["map"]["tokens"]} if state["combat"]["map"] else {}
    )
    thrain, goblin = tokens.get("Thrain"), tokens.get("Gobelin")
    if (
        thrain
        and goblin
        and max(abs(thrain["x"] - goblin["x"]), abs(thrain["y"] - goblin["y"])) > 2
    ):
        problems.append(
            f"Thrain at {thrain['x']},{thrain['y']}, goblin at {goblin['x']},{goblin['y']}"
        )
    return problems


def prepared(calls: list[Call], state: State) -> list[str]:
    problems = needs(calls, "save_monster", "plan_encounter")
    if not any(
        mentions(c, "name", "hibou") or mentions(c, "name", "owl")
        for c in called(calls, "save_monster")
    ):
        problems.append("no owlbear saved")
    return problems


def concentrating(calls: list[Call], state: State) -> list[str]:
    problems = needs(calls, "set_concentration")
    if not sheet(state, "Aria").get("concentration"):
        problems.append("Aria concentrates on nothing")
    return problems


def prepared_campaign(calls: list[Call], state: State) -> list[str]:
    """A new campaign, both characters with their players, and check_campaign's
    final word: ready to play, or what is still left."""
    problems = needs(calls, "create_campaign", "check_campaign")
    made = called(calls, "create_character")
    for character, player in (("Thrain", "Sylvain"), ("Aria", "Marie")):
        if not any(
            mentions(c, "name", character) and mentions(c, "player_name", player) for c in made
        ):
            problems.append(f"{character} not created for {player}")
    final = state["check"]
    if "is ready to play" not in final:
        problems += [line[2:] for line in final.splitlines() if line.startswith("- ")]
    return problems


def shoved(calls: list[Call], state: State) -> list[str]:
    problems = needs(calls, "roll_dice")
    prone = "prone" in fighter(state, "Gobelin").get("conditions", [])
    if called(calls, "set_condition") and not prone:
        problems.append("set_condition did not leave the goblin prone")
    return problems


SCENARIOS = [
    Scenario(
        "new_campaign",
        [
            (
                "Sylvain",
                "Salut ! On voudrait commencer une nouvelle campagne de Donjons et Dragons, "
                "on n'y a jamais joué. Moi c'est Sylvain, je veux jouer Thrain, un guerrier nain.",
            ),
            (
                "Marie",
                "Et moi c'est Marie, je veux jouer Aria, une magicienne elfe. Pour le reste, "
                "choisis pour nous : une aventure classique, dans une crypte.",
            ),
            ("Sylvain", "Parfait. Prépare tout ce qu'il faut et dis-nous quand on commence."),
        ],
        prepared_campaign,
        fresh=True,
    ),
    Scenario(
        "seating",
        [
            ("Sylvain", "Bonsoir tout le monde ! C'est Sylvain, je joue Thrain comme d'habitude."),
            ("Marie", "Salut ! Moi c'est Marie, je joue Aria."),
        ],
        seated,
    ),
    Scenario(
        "npc",
        [("Marie", "Aria va voir Mara l'aubergiste et lui demande ce qu'elle sait de la cloche.")],
        asked_mara,
        [SEATED],
    ),
    Scenario(
        "attack",
        [("Sylvain", "J'attaque le gobelin avec ma hache d'armes !")],
        attacked,
        [SEATED, FIGHT],
    ),
    Scenario(
        "spell",
        [
            (
                "Marie",
                "Aria lance Projectile magique sur le gobelin, avec un emplacement de niveau 1.",
            )
        ],
        magic_missile,
        [SEATED, FIGHT, ("next_turn", {})],
    ),
    Scenario(
        "end_turn",
        [("Sylvain", "C'est bon, j'ai fini mon tour.")],
        turn_passed,
        [SEATED, FIGHT],
    ),
    Scenario(
        "short_rest",
        [("Sylvain", "On s'arrête une heure pour souffler. Thrain dépense deux dés de vie.")],
        short_rest,
        [SEATED, ("update_character", {"name_or_id": "Thrain", "hit_points_current": 8})],
    ),
    Scenario(
        "item",
        [("Marie", "Aria ramasse la dague du gobelin et la range dans son sac.")],
        picked_up,
        [SEATED],
    ),
    Scenario(
        "search",
        [("Sylvain", "Thrain fouille la pièce à la recherche de pièges.")],
        searched,
        [SEATED],
    ),
    Scenario(
        "map_move",
        [("Sylvain", "Thrain avance vers le gobelin, aussi loin qu'il peut.")],
        charged,
        [SEATED, ("set_battlefield", {"width": 8, "height": 6}), FIGHT],
    ),
    Scenario(
        "prepare_monster",
        [("Sylvain", "MJ, pour la suite, prépare-nous une rencontre avec un ours-hibou.")],
        prepared,
        [SEATED],
    ),
    Scenario(
        "concentration",
        [("Marie", "Aria lance Détection de la magie et garde sa concentration dessus.")],
        concentrating,
        [SEATED],
    ),
    Scenario(
        "shove",
        [("Sylvain", "Thrain bouscule le gobelin pour le faire tomber à terre.")],
        shoved,
        [SEATED, FIGHT],
    ),
]
