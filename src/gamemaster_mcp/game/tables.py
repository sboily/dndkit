"""D&D 5e (2014) reference tables: numbers only, read by ``rules``."""

# Monster XP by challenge rating (DMG ch. 9 / basic rules).
XP_BY_CHALLENGE: dict[str, int] = {
    "0": 10, "1/8": 25, "1/4": 50, "1/2": 100, "1": 200, "2": 450, "3": 700,
    "4": 1100, "5": 1800, "6": 2300, "7": 2900, "8": 3900, "9": 5000, "10": 5900,
    "11": 7200, "12": 8400, "13": 10000, "14": 11500, "15": 13000, "16": 15000,
    "17": 18000, "18": 20000, "19": 22000, "20": 25000, "21": 33000, "22": 41000,
    "23": 50000, "24": 62000, "25": 75000, "26": 90000, "27": 105000,
    "28": 120000, "29": 135000, "30": 155000,
}  # fmt: skip

# XP thresholds per character level: easy, medium, hard, deadly (DMG ch. 3).
DIFFICULTY_THRESHOLDS: dict[int, tuple[int, int, int, int]] = {
    1: (25, 50, 75, 100), 2: (50, 100, 150, 200), 3: (75, 150, 225, 400),
    4: (125, 250, 375, 500), 5: (250, 500, 750, 1100), 6: (300, 600, 900, 1400),
    7: (350, 750, 1100, 1700), 8: (450, 900, 1400, 2100), 9: (550, 1100, 1600, 2400),
    10: (600, 1200, 1900, 2800), 11: (800, 1600, 2400, 3600),
    12: (1000, 2000, 3000, 4500), 13: (1100, 2200, 3400, 5100),
    14: (1250, 2500, 3800, 5700), 15: (1400, 2800, 4300, 6400),
    16: (1600, 3200, 4800, 7200), 17: (2000, 3900, 5900, 8800),
    18: (2100, 4200, 6300, 9500), 19: (2400, 4900, 7300, 10900),
    20: (2800, 5700, 8500, 12700),
}  # fmt: skip

# Encounter multipliers, from one monster up (DMG ch. 3); a small party uses the
# next step up, a large party the next step down.
ENCOUNTER_MULTIPLIERS = (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0)

# XP needed to reach each level (PHB ch. 1).
XP_FOR_LEVEL: dict[int, int] = {
    1: 0, 2: 300, 3: 900, 4: 2700, 5: 6500, 6: 14000, 7: 23000, 8: 34000,
    9: 48000, 10: 64000, 11: 85000, 12: 100000, 13: 120000, 14: 140000,
    15: 165000, 16: 195000, 17: 225000, 18: 265000, 19: 305000, 20: 355000,
}  # fmt: skip

# Spell slots per slot level for a full caster of each level (PHB ch. 3).
FULL_CASTER_SLOTS: dict[int, tuple[int, ...]] = {
    1: (2,), 2: (3,), 3: (4, 2), 4: (4, 3), 5: (4, 3, 2), 6: (4, 3, 3),
    7: (4, 3, 3, 1), 8: (4, 3, 3, 2), 9: (4, 3, 3, 3, 1), 10: (4, 3, 3, 3, 2),
    11: (4, 3, 3, 3, 2, 1), 12: (4, 3, 3, 3, 2, 1), 13: (4, 3, 3, 3, 2, 1, 1),
    14: (4, 3, 3, 3, 2, 1, 1), 15: (4, 3, 3, 3, 2, 1, 1, 1),
    16: (4, 3, 3, 3, 2, 1, 1, 1), 17: (4, 3, 3, 3, 2, 1, 1, 1, 1),
    18: (4, 3, 3, 3, 3, 1, 1, 1, 1), 19: (4, 3, 3, 3, 3, 2, 1, 1, 1),
    20: (4, 3, 3, 3, 3, 2, 2, 1, 1),
}  # fmt: skip

# Warlock pact magic per level: (number of slots, slot level).
PACT_SLOTS: dict[int, tuple[int, int]] = {
    1: (1, 1), 2: (2, 1), 3: (2, 2), 4: (2, 2), 5: (2, 3), 6: (2, 3), 7: (2, 4),
    8: (2, 4), 9: (2, 5), 10: (2, 5), 11: (3, 5), 12: (3, 5), 13: (3, 5),
    14: (3, 5), 15: (3, 5), 16: (3, 5), 17: (4, 5), 18: (4, 5), 19: (4, 5),
    20: (4, 5),
}  # fmt: skip

# Class -> (hit die, spellcasting progression).
CLASSES: dict[str, tuple[int, str]] = {
    "artificer": (8, "half_up"),
    "barbarian": (12, "none"),
    "bard": (8, "full"),
    "cleric": (8, "full"),
    "druid": (8, "full"),
    "fighter": (10, "none"),
    "monk": (8, "none"),
    "paladin": (10, "half"),
    "ranger": (10, "half"),
    "rogue": (8, "none"),
    "sorcerer": (6, "full"),
    "warlock": (8, "pact"),
    "wizard": (6, "full"),
}

# Class names as players say them, French included (both translations of warlock).
CLASS_ALIASES: dict[str, str] = {
    "artificier": "artificer",
    "barbare": "barbarian",
    "barde": "bard",
    "clerc": "cleric",
    "pretre": "cleric",
    "druide": "druid",
    "guerrier": "fighter",
    "moine": "monk",
    "rodeur": "ranger",
    "roublard": "rogue",
    "voleur": "rogue",
    "ensorceleur": "sorcerer",
    "occultiste": "warlock",
    "sorcier": "warlock",
    "magicien": "wizard",
    "mage": "wizard",
}
