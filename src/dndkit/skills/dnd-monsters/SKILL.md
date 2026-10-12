---
name: dnd-monsters
description: Create the monsters and bosses a D&D 5e story needs with the dndkit tools, sized to the party at the table, prepare the fight, and run a boss's legendary actions and resistances. Activate before inventing a creature or preparing an encounter.
allowed_tools:
  - save_monster
  - plan_encounter
---

# Monsters and bosses

You are the game master: the creatures of your story are yours to invent. Do
not ask the players for a monster's statistics, and do not stop because the
bestiary lacks one. Create it, then rate the fight.

## Book monsters first

A goblin, an orc, an ogre or a young dragon has its numbers in the Monster
Manual (or the SRD): give them to `save_monster` (a goblin is AC 15, 7 hit
points, challenge 1/4). The challenge-rating table below is for creatures you
invent: at low challenge ratings it gives far more hit points than the book's
monsters have (a challenge 1/4 creature gets 42).

## Inventing a creature

- `save_monster` with a `name`, a `challenge_rating`, and its `size` and
  `speed` ("30 ft., fly 60 ft."). The challenge rating alone fills armor
  class and hit points from the DMG's table, and an `actions` line giving its
  attack bonus, the damage it should deal in a round and its save DC.
- Then write its `actions` in that frame: one to three attacks at that bonus
  whose damage adds up to the round's total, and a signature ability with a
  saving throw at that DC ("Breath of ash, recharge 5-6: 15-ft cone, DC 15
  Dexterity save, 6d6 fire, half on a success").
- Give it a weakness or a habit the players can find, in `notes`.
- To make it sturdier or deadlier, trade: more armor or hit points for less
  damage, and the reverse, so the challenge rating still fits.
- Monsters already in the bestiary: `get_monsters` shows the stat block, to
  narrate their attacks as written.

## Sizing a fight to the party

- `plan_encounter` with the monsters and how many: it rates the fight
  against the characters at the table (`seat_players`), and says the XP.
- Aim for medium or hard for an ordinary fight, deadly only for a climax.
- The rating counts every monster. The DMG leaves out minions far weaker than
  the others when they hardly threaten: a boss with a few rats is rated a
  little harder than it plays.
- A challenge 0 creature is worth 10 XP; one with no attack worth having (a
  frog, a crab) is worth 0: give `xp` 0 to `save_monster`.
- A boss alone against four characters of level L: challenge rating about
  L + 2. Against two or three characters: about L. Add a few weak minions
  rather than raising the boss.
- Read the characters' hit points and armor first (`get_game_state`,
  `get_character`): a party with 10 hit points each falls fast.

## Bosses

- `save_monster` with `boss: true` crowns it on the screens and makes it a
  legendary creature: 3 legendary actions a round and 3 legendary
  resistances a day, unless you set `legendary_actions` and
  `legendary_resistances`. Write its legendary options in `actions`, each
  with its cost ("Tail swipe (1), Ash cloud (2)").
- Legendary actions: at the end of another creature's turn, the boss may take
  one option; call `use_legendary` with its `cost`. They come back at the
  start of the boss's own turn, never during it.
- Legendary resistance: when the boss fails a saving throw that would end the
  fight too soon, it may succeed instead; call `use_legendary` with
  `resistance: true` and say it shrugs the effect off.
- In its lair, the boss may also act on initiative count 20 (lair actions):
  narrate them, there is no tool for them.
- Give the boss a moment: a line when it enters, a change of tactics when it
  is bloodied (half its hit points), a last word.

## Running the fight

- `start_combat` with the encounter. The characters at the table join with
  initiative rolled for them, unless you give them as `participants`. On a
  battle map, the monsters can wait at their planned squares, hidden for an
  ambush (the `dnd-battle-map` skill).
- Too many or too few once it starts? `remove_combatant` with `reason:
  withdrawn` takes a monster back (no XP, off the map); `add_combatant`
  brings reinforcements. Before it starts, change the plan instead:
  `plan_encounter` with the new count.
- Roll every attack and damage with `roll_dice`, record hits with
  `change_hit_points`; a monster at 0 leaves the fight on its own.
- `end_combat` gives the XP to award with `award_experience`.
