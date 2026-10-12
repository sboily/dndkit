"""Short rules reminders (D&D 5e 2014), paraphrased, findable by English or French name."""

from gamemaster_mcp.errors import NotFoundError
from gamemaster_mcp.text import normalize

RULES: dict[str, str] = {
    "blinded": "Can't see; fails any check that needs sight. Attacks against it have "
    "advantage, its own attacks have disadvantage.",
    "charmed": "Can't attack the charmer or target it with harmful abilities or magic. "
    "The charmer has advantage on social checks against it.",
    "deafened": "Can't hear; fails any check that needs hearing.",
    "frightened": "Disadvantage on ability checks and attack rolls while the source of its "
    "fear is in sight; can't willingly move closer to it.",
    "grappled": "Speed 0. Ends if the grappler is incapacitated or an effect moves the "
    "creature out of reach. Escape: an action, Athletics or Acrobatics against the "
    "grappler's Athletics.",
    "incapacitated": "Can't take actions or reactions.",
    "invisible": "Can't be seen without magic or a special sense. Attacks against it have "
    "disadvantage, its own attacks have advantage.",
    "paralyzed": "Incapacitated, can't move or speak; fails Strength and Dexterity saves. "
    "Attacks against it have advantage, and a hit from within 5 feet is a critical hit.",
    "petrified": "Turned to stone: incapacitated, can't move or speak, unaware. Attacks "
    "against it have advantage; fails Strength and Dexterity saves; resistance to all "
    "damage; immune to poison and disease (any already in it is suspended).",
    "poisoned": "Disadvantage on attack rolls and ability checks.",
    "prone": "Can only crawl, or stand up for half its movement. Disadvantage on its "
    "attacks. Attacks against it have advantage within 5 feet, disadvantage beyond.",
    "restrained": "Speed 0. Attacks against it have advantage, its attacks have "
    "disadvantage; disadvantage on Dexterity saves.",
    "stunned": "Incapacitated, can't move, speaks falteringly; fails Strength and Dexterity "
    "saves. Attacks against it have advantage.",
    "unconscious": "Incapacitated, can't move or speak, unaware; drops what it holds and "
    "falls prone; fails Strength and Dexterity saves. Attacks against it have advantage, "
    "and a hit from within 5 feet is a critical hit.",
    "exhaustion": "Levels add up: 1 disadvantage on ability checks; 2 speed halved; "
    "3 disadvantage on attacks and saves; 4 hit point maximum halved; 5 speed 0; "
    "6 death. A long rest with food and drink removes one level.",
    "advantage": "Roll two d20 and keep the higher (disadvantage: the lower). Several "
    "sources don't stack; having both cancels them out.",
    "death saves": "At 0 HP, roll a d20 at the start of each turn: 10 or more is a "
    "success, less a failure. Three successes: stable. Three failures: dead. A 1 counts "
    "as two failures; a 20 brings the creature back with 1 HP. Taking damage at 0 HP is "
    "a failure (two on a critical hit). Damage left over after 0 HP that equals or "
    "exceeds the hit point maximum kills outright.",
    "stabilizing": "An action and a DC 10 Wisdom (Medicine) check stabilize a creature at "
    "0 HP. A stable creature regains 1 HP after 1d4 hours.",
    "short rest": "At least one hour. Each character may spend Hit Dice: roll each, add "
    "the Constitution modifier, regain that many hit points. Warlocks regain pact slots.",
    "long rest": "At least eight hours, once per 24 hours, starting with at least 1 HP: "
    "regain all hit points, spell slots and half the total Hit Dice (at least one).",
    "cover": "Half cover: +2 to AC and Dexterity saves. Three-quarters cover: +5. Total "
    "cover: can't be targeted directly.",
    "concentration": "One concentration spell at a time. Taking damage calls for a "
    "Constitution save, DC 10 or half the damage if higher; failing ends the spell. "
    "Being incapacitated or killed ends it too.",
    "opportunity attack": "When a visible enemy leaves your reach, you may use your "
    "reaction for one melee attack. The Disengage action, teleporting or being moved "
    "against one's will doesn't provoke it.",
    "grapple": "Replaces one attack: Athletics against the target's Athletics or "
    "Acrobatics; the target is at most one size larger. Success: the target is grappled.",
    "shove": "Replaces one attack: Athletics against Athletics or Acrobatics; the "
    "target is at most one size larger. Success knocks it prone or pushes it 5 feet away.",
    "surprise": "Creatures that notice no threat at the start are surprised: no move, "
    "action or reaction on their first turn.",
    "initiative": "Each combatant makes a Dexterity check (d20 + Dexterity modifier); "
    "turns go from highest to lowest. The game master settles ties.",
    "actions": "In combat a creature can Attack, Cast a Spell, Dash (extra movement), "
    "Disengage (no opportunity attacks), Dodge (attacks against it have disadvantage), "
    "Help (an ally gains advantage), Hide, Ready a reaction, Search or Use an Object, plus "
    "its movement and possibly one bonus action and one reaction per round.",
    "two-weapon fighting": "After attacking with a light melee weapon, a bonus action "
    "attack with another light melee weapon; no ability modifier to its damage unless "
    "negative.",
    "critical hit": "A natural 20 on an attack roll always hits; roll all the damage dice "
    "twice, then add modifiers once.",
    "falling": "1d6 bludgeoning damage per 10 feet fallen, up to 20d6; the creature lands prone.",
    "suffocating": "Breath can be held for 1 + Constitution modifier minutes (at least 30 "
    "seconds); after that, the creature lasts Constitution modifier rounds (at least 1) "
    "before dropping to 0 HP.",
    "difficult terrain": "Each foot of movement costs one extra foot.",
    "obscured areas": "Lightly obscured (dim light, fog): disadvantage on Perception by "
    "sight. Heavily obscured (darkness, thick fog): effectively blinded.",
    "inspiration": "A character with inspiration may spend it for advantage on one attack "
    "roll, saving throw or ability check.",
    "encounter difficulty": "Add the monsters' XP, multiply by a factor for their number "
    "(x1 for one, x1.5 for two, x2 for 3-6, x2.5 for 7-10, x3 for 11-14, x4 for 15+), "
    "and compare with the party's easy, medium, hard and deadly thresholds.",
}

ALIASES: dict[str, str] = {
    "aveugle": "blinded", "charme": "charmed", "assourdi": "deafened", "sourd": "deafened",
    "effraye": "frightened", "terrorise": "frightened", "agrippe": "grappled",
    "empoigne": "grappled", "neutralise": "incapacitated", "incapable d'agir": "incapacitated",
    "paralyse": "paralyzed", "petrifie": "petrified", "empoisonne": "poisoned",
    "a terre": "prone", "entrave": "restrained", "etourdi": "stunned",
    "inconscient": "unconscious", "epuisement": "exhaustion", "desavantage": "advantage",
    "disadvantage": "advantage", "jets contre la mort": "death saves",
    "jet contre la mort": "death saves", "death saving throws": "death saves",
    "stabiliser": "stabilizing", "repos court": "short rest", "repos long": "long rest",
    "abri": "cover", "couverture": "cover", "attaque d'opportunite": "opportunity attack",
    "lutte": "grapple", "agripper": "grapple", "bousculer": "shove", "pousser": "shove",
    "combat a deux armes": "two-weapon fighting", "coup critique": "critical hit",
    "critique": "critical hit", "chute": "falling", "suffocation": "suffocating",
    "asphyxie": "suffocating", "terrain difficile": "difficult terrain",
    "visibilite": "obscured areas", "obscurite": "obscured areas",
    "actions en combat": "actions", "difficulte des rencontres": "encounter difficulty",
}  # fmt: skip

_INDEX = {normalize(key): key for key in RULES} | {
    normalize(alias): key for alias, key in ALIASES.items()
}


def lookup(topic: str) -> tuple[str, str]:
    """The rule a topic names, as (topic, text); plural and French names work too."""
    wanted = normalize(topic)
    key = _INDEX.get(wanted) or _INDEX.get(wanted.rstrip("s"))
    if key is None:
        matches = [k for name, k in _INDEX.items() if wanted and wanted in name]
        key = matches[0] if len(set(matches)) == 1 else None
    if key is None:
        raise NotFoundError(f"No rule note on '{topic}'. Topics: {', '.join(RULES)}.")
    return key, RULES[key]
