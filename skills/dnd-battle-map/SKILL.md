---
name: dnd-battle-map
description: Run a D&D 5e fight on a grid battle map with the Gamemaster tools - lay out the room, place combatants, move them by the rules (speed, terrain, opportunity attacks). Activate when a fight starts where positions matter.
allowed_tools:
  - set_battlefield
  - place_tokens
  - move_token
---

# Fighting on the battle map

The map is a grid of 5-foot squares named like a chessboard: a column letter
and a row number, A1 at the top left. The players see it on the table screen
and on their phones; you only read it through the tools, so never guess a
position or a distance: `get_game_state` lists every square and the distances
from whoever is acting, and every move says who is now in reach.

## Set the scene

- Use a map when position matters: several foes, cover, a corridor, a ledge.
  A duel or a brawl can stay in words.
- Turn your description into `set_battlefield`: width and height in squares
  (a 30-foot room is 6 squares), walls and pillars as `walls`, rubble, mud or
  undergrowth as `difficult`. Blocks are written `C1:C6`.
- `start_combat` places everyone with no square yet: the party on the left
  edge, its foes on the right. Use `place_tokens` for an ambush or a
  formation; a big creature is placed by its top-left square.
- Save monsters with their `size` and `speed` (`save_monster`) first: a Large
  ogre holds 2x2 squares, and the speed decides how far it goes.

## Each turn

- When a player says where they go, call `move_token`:
  - "I charge the goblin" -> `toward`: it stops within reach, or as close as
    it can and says how far it still is;
  - "I back off" -> `away_from`, with `feet` if they say how far;
  - "I go to D7" -> `to`; it is refused if they cannot afford it: say so and
    offer the Dash action, or to go toward it.
- Dash (`dash`) doubles this turn's movement; Disengage (`disengage`) means
  no opportunity attack. A prone character stands up first, for half their
  speed; grappled or restrained ones cannot move.
- When the result lists opportunity attacks, resolve them right away: the
  foe attacks the mover (`roll_dice`), then the move goes on.
- Shoves, Thunderwave, Misty Step and other pushes, pulls or teleports use
  `forced`: no movement spent, no opportunity attack. A push stops at a wall
  or a creature.
- Move monsters on their turns too, sensibly: toward the nearest or weakest
  character, away when they flee.
- Ranges come from the distances the tools give: a ranged attack has
  disadvantage beyond its normal range, or with a foe adjacent.
- `next_turn` gives the next combatant its full movement.

## Speaking about it

Say squares only when the players use them; otherwise describe ("you reach
the goblin by the pillar"). The players' French books count in metres: 5 feet
is 1.5 metres, so 30 feet is 9 metres.
