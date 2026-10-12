# dndkit

A [Model Context Protocol](https://modelcontextprotocol.io) server that lets an
AI be the game master of a Dungeons & Dragons 5e campaign: it keeps the
characters, the world, the fights and the dice, and holds the rules, so the
model narrates while the server keeps count. It is built with
[FastMCP](https://gofastmcp.com) 4 and made for **voice play with several
players around one microphone**, as an MCP service in
[roomkit-ui](https://github.com/roomkit-live/roomkit-ui), while working just as
well from Claude Desktop or any MCP client, with a cloud model or a local one.

dndkit began as a fork of
[study-flamingo/gamemaster-mcp](https://github.com/study-flamingo/gamemaster-mcp)
by Joel Casimir, and has since been largely rewritten: voice play with several
players, rules kept by the server (combat, the battle map, hit dice,
concentration, a campaign checked before play), skills, on-screen widgets and
live web pages. It took a name of its own so as not to take the original
project's. See [CHANGELOG.md](CHANGELOG.md) for what changed.

## What it does

- **Campaigns**: several campaigns, one active at a time, each saved as one JSON
  file. Creating a campaign never overwrites an existing one; deleting one takes
  a confirmation code and moves its file to a trash folder.
- **Characters**: full 5e sheets; damage and healing with temporary hit points
  applied first, unconsciousness and death saves at 0 HP, massive damage;
  conditions and exhaustion; inventory that stacks; known spells and spell slots;
  short and long rests; experience and levelling up (hit points, proficiency,
  spell slots by class, French class names understood).
- **Combat**: party characters and monsters in one initiative order, tracked by
  position so three "Goblin"s become "Goblin 1/2/3"; monster hit points, AC and
  conditions; a monster at 0 HP leaves the fight; newcomers mid-fight; the end of
  the fight sums the XP of the defeated.
- **Bestiary and encounters**: saved stat blocks fill monsters in; planned
  encounters are rated easy to deadly against the party (DMG rules) and started
  with one call, their initiative rolled.
- **World**: NPCs (with private bios), locations and quests with numbered objectives.
- **Journal**: session notes and a per-campaign adventure log with search.
- **Dice and rules**: `d20`, `1d20+5`, `2d6+1d4+3`, advantage and disadvantage;
  short rule reminders (conditions, cover, grapple, death saves...) by English
  or French name.
- **Several players**: each spoken turn names its speaker; a roll call says
  who plays which character tonight, and only the characters at the table
  count for difficulty and XP.
- **Battle map**: a grid where moves follow the 5e rules (speed, terrain,
  opportunity attacks), areas of effect, cover, hidden foes.
- **Before play**: `check_campaign` says what breaks the rules or is missing
  in a new campaign, each with the tool that fixes it.
- **Skills**: how-to guides the model loads when it needs them: being the
  game master and preparing a campaign, monsters and bosses, the battle map.
- **On-screen widgets** (MCP Apps): rolling dice, a live combat tracker, a party
  board, the table and character sheets, in clients that show MCP Apps.
- **Live web pages**: a table screen, each player's sheet on their phone, and
  a backstage where you follow every call the model makes.

Names are matched without case or accents ("elodie" finds "Élodie"), and a part
of a name is enough when only one name contains it ("phare" finds "Le phare
éteint"), the way a speech transcript spells them. When a call fails, the error
says why and lists the known names, so the model can correct itself.

## Install and run

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
# From PyPI
uvx dndkit

# Straight from GitHub
uvx --from git+https://github.com/sboily/dndkit dndkit

# From a checkout
git clone https://github.com/sboily/dndkit.git
cd dndkit
uv sync
uv run dndkit
```

The server speaks MCP over stdio: an MCP client starts it, you don't keep it
running yourself. `uvx` fetches it on first use and keeps it cached. To run it
as a server of its own, for several computers or on a home server, see
[Docker](#docker).

### Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `DNDKIT_STORAGE_DIR` | the per-user data directory (below) | Where campaigns are stored |
| `DNDKIT_LOG_LEVEL` | `INFO` | Log level; logs go to stderr |
| `DNDKIT_WEB_PORT` | unset: no web pages | Serve the [live web pages](#live-web-pages) on this port; the players' join codes (`show_join_codes`) need them |
| `DNDKIT_WEB_HOST` | `127.0.0.1` | `0.0.0.0` lets phones on the same network open them, and scan their join codes |
| `DNDKIT_WEB_URL` | guessed | The address phones should use, when the server cannot tell (a DNS name, Tailscale) |
| `DNDKIT_TRANSPORT` | `stdio` | `http`: a server of its own, MCP at `/mcp` (Streamable HTTP) and `/health` |
| `DNDKIT_HTTP_HOST` | `127.0.0.1` | Where HTTP listens; beyond this machine it takes a token |
| `DNDKIT_HTTP_PORT` | `8000` | The HTTP port |
| `DNDKIT_HTTP_TOKEN` | unset | The token every MCP request must carry (`Authorization: Bearer ...`); 16 characters at least, `openssl rand -hex 32` makes one |

Default data directory:

- macOS: `~/Library/Application Support/dndkit`
- Linux: `~/.local/share/dndkit` (or `$XDG_DATA_HOME/dndkit`)
- Windows: `%LOCALAPPDATA%\dndkit`

Before its rename the project was `gamemaster-mcp`: its `GAMEMASTER_*`
variables still work, and its data directory is used as long as no `dndkit`
one exists.

To start a campaign from a prepared world document, drop a `.md` or `.txt` file
in the `settings/` folder of the data directory and pass its name as
`setting_file` to `create_campaign` or `update_campaign`. Only files directly in
that folder can be read.

### With roomkit-ui

In **Settings → Integrations → MCP**, add a server:

| Field | Value |
| --- | --- |
| Name | `dndkit` |
| Transport | `stdio` |
| Command | `uvx` |
| Arguments | `dndkit` (from PyPI), or `--from git+https://github.com/sboily/dndkit dndkit` |
| Environment variables | `DNDKIT_STORAGE_DIR=/Users/you/Games/dnd` (optional)<br>`DNDKIT_WEB_PORT=8765` and `DNDKIT_WEB_HOST=0.0.0.0` for the web pages and the players' join codes on their phones (optional) |

From a local checkout instead: Command `uv`, Arguments
`run --directory /path/to/dndkit dndkit`.

roomkit-ui reads what the server publishes besides its tools: its skills
(roomkit 0.98 and later) and its instructions, which tell the model how the
tools are meant to be used (roomkit 0.99). Put the system prompt below in the
assistant's personality.

The 63 tool schemas weigh about 8,950 tokens by roomkit's own estimate, over
the 8,000 at which roomkit may hide tools behind `find_tools`: keep the skills
on (the tools they bring then wait for them: about 7,350 tokens), or raise
roomkit's threshold (`tool_search_threshold_tokens`). roomkit-ui's automatic
Tool Search leaves a local voice model every tool. Optional parameters are
advertised without their `null` alternative to save room.

#### Local models

A model running on your own computer can be the game master. The
[local model bench](poc/local-model/RESULTS.md) plays scripted table turns
through roomkit with Ornith 1.5 35B-A3B (llama.cpp): with **thinking on** it
passes 26 to 30 of 36 scenarios; without thinking it mostly narrates instead
of calling the tools. Tool Search hurts such a model: leave every tool in
sight. A thinking turn takes about a minute, which roomkit-ui's background
tasks (on a llama.cpp model of their own) keep away from the voice.

#### Skills

The server ships three Agent Skills, how-to guides the model loads when it
needs them, and publishes them by the official MCP Skills extension
([SEP-2640](https://modelcontextprotocol.io/seps/2640-skills-extension),
`io.modelcontextprotocol/skills`): it declares the extension in its
capabilities, serves every skill file as a `skill://<name>/<file>` resource,
and answers `skills/list` and `skills/get` with each skill's frontmatter and
the SHA-256 digest and size of its files. The server instructions also point
at each skill's URI, for hosts that only read resources. Load
`dnd-game-master` first: the system prompt below asks for it.

| Skill | Teaches | Gates (roomkit) |
| --- | --- | --- |
| `dnd-game-master` | To load first: the game master leads and acts, what the tools hold, opening and ending a session, a session zero by the rules (scores, armor, weapon, skills and spells for each class), `check_campaign` before play | nothing |
| `dnd-monsters` | Inventing monsters and bosses sized to the party, preparing and rating a fight, legendary actions and resistances, lair actions | `save_monster`, `plan_encounter` |
| `dnd-battle-map` | Fights on the grid: laying out the room, placing and hiding combatants, moving by the rules, areas of effect, cover | `set_battlefield`, `place_tokens`, `move_token`, `area_of_effect`, `check_target` |

A skill's `allowed_tools` frontmatter is roomkit's: roomkit keeps those tools
out of the catalogue, and out of its token count, until the model activates
the skill. With the skills on, the catalogue weighs about 7,350 tokens.
roomkit-ui lists them under the server's name; a client that does not speak
the extension can load them from `src/dndkit/skills/` as a skill folder.

### Docker

The image runs dndkit as a server of its own: MCP over HTTP on port 8000 and
the web pages on 8765, campaigns in a volume. It suits a table that plays from
several computers, or a server that stays on (a NAS, a Raspberry Pi: the image
is built for amd64 and arm64).

```bash
curl -O https://raw.githubusercontent.com/sboily/dndkit/main/compose.yaml
echo "DNDKIT_HTTP_TOKEN=$(openssl rand -hex 32)" > .env
echo "DNDKIT_WEB_URL=http://192.168.1.20:8765" >> .env   # this computer on your network
docker compose up -d
docker compose logs dndkit | grep Backstage   # the game master's link
```

The image sets `DNDKIT_TRANSPORT=http`, `DNDKIT_HTTP_HOST=0.0.0.0`,
`DNDKIT_HTTP_PORT=8000`, `DNDKIT_WEB_HOST=0.0.0.0`, `DNDKIT_WEB_PORT=8765` and
`DNDKIT_STORAGE_DIR=/data`; `compose.yaml` adds `DNDKIT_HTTP_TOKEN` and
`DNDKIT_WEB_URL` from `.env`. Any other setting from the table above goes in
the service's `environment`.

In roomkit-ui, add the server with Transport `streamable_http`, URL
`http://<the server's address>:8000/mcp`, and the header
`Authorization: Bearer <the token from .env>`. The server refuses any request
without that token, and does not start listening beyond its machine without
one.

`DNDKIT_WEB_URL` is the address the players' QR codes carry. Inside a
container the server only knows its own addresses, which phones cannot reach
(the log's "Phones on this network" names one): without the setting, the codes
are right only when the table screen is opened at the server's network
address, never at `localhost`.

The backstage cannot tell the computer running Docker from any other (every
visitor comes through Docker's gateway), so it opens with its link instead,
`/gm/<code>/`, which the server writes in its log at each start: keep it to
yourself, it shows everything. The code comes from the secret in the data
volume, like the players' links.

From a checkout, `docker compose up -d --build` builds the image instead of
pulling `ghcr.io/sboily/dndkit` (published with each release from 0.5.0 on).

### With Claude Desktop

```json
{
  "mcpServers": {
    "dndkit": {
      "command": "uvx",
      "args": ["dndkit"],
      "env": { "DNDKIT_STORAGE_DIR": "/Users/you/Games/dnd" }
    }
  }
}
```

## System prompt for a voice game master

```markdown
You are the game master of a Dungeons & Dragons 5e session played by voice.
Speak the players' language, in short spoken sentences: no lists, no markdown.
You lead the game: you decide when a roll is needed, make it and apply it
with the tools, without asking leave. Before anything else, activate the
dnd-game-master skill.

Several players sit around one microphone; each of their turns opens with
who said it. Open every session the same way:
- Greet the table and ask who is playing tonight. When a voice is not named
  yet, ask who it is and call name_speaker.
- Call seat_players with start_over and each player with their character.
  Someone new gets a character first: create_character with their name as
  player_name.
- Remind the table where the last session ended (get_sessions), then play.
Call seat_players again when someone arrives or leaves. A player's "I attack"
is their character's action; speak to players by name and to characters in
the story. Absent players' characters stay in the background.

The dndkit tools hold the campaign. Trust them over your memory:
- Before describing a character, place or quest, read it (get_character,
  get_location, get_quest, get_game_state).
- Record every change as it happens: damage and healing with change_hit_points
  (characters and monsters), conditions with set_condition, a spell held
  with set_concentration (damage then asks for the save), items with
  add_item_to_character and remove_item_from_character, spells with
  use_spell_slot, the party's location and date with update_game_state.
- Roll every die with roll_dice and say the result; never invent a roll.
  Resolve each roll yourself: the attack against the target's AC, then the
  damage, applied with change_hit_points. Never ask the players for a total
  or a number the tools hold (get_character gives bonuses, spell attack and
  save DC).
  What the players must not see (a hidden foe's Stealth, an NPC's lie) is a
  secret roll: say only what it means.
- Ability checks and saves use the sheet's bonuses (get_character); a short
  rest spends Hit Dice with rest and hit_dice.
- In combat, start_combat with everyone's initiative (or a planned encounter),
  then next_turn after each turn. Monsters at 0 HP leave the fight on their own.
  When positions matter, play it on the battle map (the dnd-battle-map skill:
  set_battlefield, then move_token for every move).
  At the end, end_combat, then award_experience with the XP it reports.
- When you're unsure of a rule, lookup_rule.
- Never call get_screen_data: it feeds the on-screen widgets.
- Log notable moments with add_event, and summarise the session with
  add_session_note when the players stop.
- When a tool reports an unknown name, pick the right one from the names it
  lists, or ask the players; never create a duplicate.
- You run the monsters. One the story needs and the bestiary lacks is yours
  to create: save_monster with a challenge rating fitting the party (and
  boss for the boss), then plan_encounter to check the fight's difficulty.
  Spend a boss's legendary actions and resistances with use_legendary, and
  any creature's reaction (an opportunity attack, Shield) with take_reaction.
  A condition that lasts a while gets its rounds in set_condition.
- remove_from_campaign and delete_campaign work in two calls: the first
  says what would be lost and gives a code; ask the players, and call again
  with the code only after a clear yes.

Starting a new campaign, run a short session zero, one question at a time:
the campaign's name and pitch, then each player's character (name, race,
class, level, ability scores, then their skills with update_character), the
starting location, a first NPC and a first quest, creating each with its tool
as soon as you have it (the dnd-game-master skill has the rules for each).
Then call check_campaign and fix what it lists before the first scene.
```

## Tools

| Area | Tools |
| --- | --- |
| Campaign | `create_campaign`, `get_campaign_info`, `check_campaign`, `list_campaigns`, `load_campaign`, `update_campaign`, `delete_campaign`, `remove_from_campaign` |
| Characters | `create_character`, `get_character` 🖥, `list_characters`, `update_character` |
| Resources | `add_item_to_character`, `remove_item_from_character`, `record_death_save`, `rest` |
| Spells | `set_spell_slots`, `use_spell_slot`, `set_known_spell` |
| Progression | `award_experience`, `level_up` |
| NPCs | `create_npc`, `get_npc`, `update_npc`, `list_npcs` |
| Locations | `create_location`, `get_location`, `update_location`, `list_locations` |
| Quests | `create_quest`, `get_quest`, `update_quest`, `list_quests` |
| Table | `seat_players` 🖥, `show_join_codes` 🖥, `get_game_state` 🖥, `update_game_state`, `change_hit_points`, `set_condition`, `set_concentration` |
| Combat | `start_combat` 🖥, `add_combatant`, `next_turn`, `remove_combatant`, `use_legendary`, `take_reaction`, `end_combat` |
| Battle map | `set_battlefield` 🖥, `place_tokens`, `move_token`, `area_of_effect`, `check_target` |
| Bestiary | `save_monster`, `get_monsters`, `plan_encounter`, `list_encounters` |
| Journal | `add_session_note`, `get_sessions`, `add_event`, `get_events` |
| Utility | `roll_dice` 🖥, `lookup_rule`, `get_screen_data` (for the widgets) |

🖥 opens an on-screen widget in clients that support MCP Apps.

`update_character` sets absolute values; `change_hit_points` applies damage or
healing to characters and monsters alike, and changes nobody if one name is
unknown. A tool that fails changes nothing, in memory or on disk.

A few rules the tools keep:

- **Before play**: `check_campaign` lists what breaks the 5e rules (hit
  points the hit dice cannot give, AC under Unarmored Defense, a caster with
  no spells) and what a first campaign forgets (a fighter without armor,
  scores left at 10, no weapon, no quest or place), each with its fix.
- **Proficiencies**: `update_character` takes skills, saving throws (English
  or French names: *Discrétion*, *Sagesse*), languages and features; a new
  character is proficient in its class's saves. The sheets give each
  proficient skill and save with its bonus. `expertise` doubles the
  proficiency of a rogue's or a bard's chosen skills, and a bard from level 2
  adds half of it to every other check, initiative included (Jack of All
  Trades).
- **Hit Dice**: `rest` with `hit_dice` spends them on a short rest (rolled on
  the dice tray, each die plus the Constitution modifier); a long rest gives
  half of them back.
- **Concentration**: `set_concentration` holds one spell. Damage then asks for
  the Constitution save (DC 10 or half the damage); 0 HP or an incapacitating
  condition ends it.
- **Secret rolls**: `roll_dice` with `secret` shows on the backstage only, not
  on the table screen, the phones or the dice widget.
- **Down at 0 HP**: three death save successes or `stabilized` (Spare the
  Dying, Medicine) leave a character stable, without death saves until hit or
  healed; sheets say dying, stable or dead.
- **Exhaustion** 4 halves the hit point maximum, 6 kills.
- **Reactions**: one a round (`take_reaction`), back at the start of the
  creature's turn; one that has reacted provokes no more opportunity attacks.
- **Timed conditions**: `set_condition` with `rounds` ends by itself at the end
  of the target's turn that many turns on; `next_turn` says so.

### Monsters and bosses

The game master invents the monsters its story needs: `save_monster` with a
challenge rating alone fills armor class, hit points and a line of attack
bonus, damage a round and save DC from the DMG's "Monster Statistics by
Challenge Rating", for the model to flesh out. `boss` marks the fight's boss,
a legendary creature with 3 legendary actions a round and 3 legendary
resistances a day unless told otherwise. In combat, `use_legendary` spends
them (actions at the end of another creature's turn, back at the start of
its own); the screens crown the boss, and the game master's show what it has
left. Combatants are found by a unique part of their name ("gardien" for
"Gardien de Magma").

Characters created without hit points or armor class get the PHB's: the
class hit die at level 1 and its average after, plus Constitution each level;
10 + Dexterity without armor. A caster gets its class's spell slots and
casting ability, and its sheet (`get_character`, the widget and the player's
page) gives the spell attack bonus and save DC; the sheet also shows the
initiative bonus, background, alignment, appearance and story, spells with
their descriptions, gear, features, proficiencies and languages.
`get_character` without a name reads whose turn it is.

The running fight keeps up with the campaign: a combatant named after a party
character (even "Fizbin the gnome") plays from that sheet, including one
created once the fight began, and a monster that joined without numbers takes
its stat block as soon as `save_monster` saves it.

### Battle map

A fight can be played on a grid of 5-foot squares named like a chessboard (a
column letter and a row number, A1 at the top left). `set_battlefield` lays it
out with walls and difficult terrain; `start_combat` puts everyone without a
square at an edge (the party left, its foes right) and `place_tokens` sets
chosen squares (an ambush). `move_token` moves a combatant by the 5e rules
(PHB ch. 9) and refuses an impossible move:

- 5 feet a square, diagonals included (the PHB grid rule), 10 in difficult
  terrain or through another creature's space; walls are walked around and
  never cut diagonally;
- allies can be passed through, foes only when two sizes apart; nobody ends a
  move on someone else; a Large creature holds 2x2 squares, Huge 3x3,
  Gargantuan 4x4 (`save_monster`'s `size`);
- speed from the sheet (25 ft for dwarves, halflings and gnomes, else 30;
  `create_character`'s `speed` overrides it) or the stat block's `speed`;
  grappled, restrained, stunned, paralyzed, petrified or unconscious: 0;
  exhaustion halves it from level 2; Dash doubles the turn's movement;
- a prone mover stands up first, for half its speed;
- leaving a foe's reach provokes an opportunity attack, which the result
  names, unless the mover Disengaged; `forced` movement (a shove, a spell, a
  teleport) spends nothing and provokes nothing;
- `toward` someone stops within reach or as close as it can ("still 15 ft
  away"); `away_from` backs off; `next_turn` restores the next combatant's
  movement.

Around the moves:

- `area_of_effect` says who a spell or a breath catches: a `sphere` (or
  cylinder) of radius R `at` a square or a creature holds every square within
  R feet as the grid counts them; a `cube` is centred there, or set against
  its `source`'s side facing `toward`; a `cone` (as wide as it is far) and a
  `line` start at the edge of the caster's space, and take a square when at
  least half of it is covered (DMG). Walls stop an area. Everyone caught is
  named, allies first; the area shows on the map until the next turn.
- `check_target` gives what an attack needs: distance, reach, cover by the
  DMG corner rule (walls give half, three-quarters or total cover, creatures
  half at most), a foe adjacent to a ranged attacker, hidden attacker or
  target.
- Hidden foes (`place_tokens` with `hidden`, or a planned group's `hidden`)
  stay off the players' screens altogether: no token, no line in the
  initiative they see, no turn named, no hole in the squares a character can
  reach. The game master's screens show them faint. `hidden: false` reveals.
- `plan_encounter` can carry a `battlefield` and, per monster group, the
  squares `at` which they start (checked against the map, its walls and each
  other); `start_combat` with that encounter lays it all out.

`remove_combatant` takes a creature out of the fight and off the map: a
`defeated` or `fled` foe counts for XP, a `withdrawn` one (a mistake, a
change of plan) leaves no trace; `add_combatant` brings one in at its side's
edge.

The model reads the map in text: `set_battlefield` and `place_tokens` return
a grid with a legend, every move says what it cost, what is left and who is
in reach, and `get_game_state` lists the squares and the distances from
whoever is acting. The combat widget and the web pages draw it: tokens gold for
the party and red for its foes, the squares the acting character can still
reach, and on a player's phone their own token ringed. The players' pages show
how hurt a foe looks, never its hit points. The map goes away with
`end_combat`.

### Who plays

roomkit-ui tells the voices apart (enrolled voices, or Meta Muse labels that
the user or the model's `name_speaker` names) and opens each spoken turn with
the speaker's name. The game keeps the rest: a character's `player_name` ties
it to a person, and `seat_players` records who is at the table tonight, in
seat order. Players are matched by name, case and accents aside; the server
keeps no voice data. Once there has been a roll call:

- `get_game_state` says who plays whom, who is absent and which characters
  nobody plays, so the model finds its way after a break;
- encounter difficulty (`plan_encounter`, `list_encounters`) counts the
  characters at the table only: two players out of four turn a medium fight
  into a deadly one;
- `award_experience` without names shares the XP between the characters at
  the table; name absent characters to include them.

Without a roll call, the whole party counts as present.

`delete_campaign` works in two calls. The first deletes nothing: it says what
the campaign holds and returns a 4-digit code valid for 5 minutes. Only a
second call with that code deletes, by moving the file to `<data dir>/trash/`,
from where it can be put back by hand. A wrong code cancels the request.

## On-screen widgets (MCP Apps)

Seven tools carry an MCP App (`_meta.ui.resourceUri`): the client opens their
page next to the conversation.

| Tool | Widget |
| --- | --- |
| `roll_dice` | Dice tray: each die tumbles and lands on its face; a natural 20 glows, a natural 1 shakes; with advantage the discarded d20 fades out; recent rolls below. |
| `start_combat`, `set_battlefield` | Combat tracker, live: the battle map when there is one, initiative order, current turn, hit point bars that flash on damage or healing, AC, conditions, the defeated and their XP. |
| `get_game_state` | Party board, live: location, date, funds, every character's hit points, spell slots, conditions and death saves, quest progress, combat banner. |
| `seat_players` | The table, live: the players seated around it with their characters, newcomers without one yet, absent players and characters nobody plays. |
| `show_join_codes` | Join codes: each character's QR code for the players' phones, the same as on the table screen, so roomkit-ui alone is enough to hand them out. Needs the web pages (`DNDKIT_WEB_PORT`, and `DNDKIT_WEB_HOST=0.0.0.0` for phones). |
| `get_character` | Character sheet, live: hit points, AC, proficiency, XP to next level, abilities, conditions, spell slots, spells, inventory. |

Each page is self-contained (no network access), French or English after the
system language, and reads its data with the `get_screen_data` tool, refreshing
every couple of seconds: the combat tracker follows `change_hit_points` or
`next_turn` calls made later in the conversation. The widgets only display; the
game changes through the conversation, so the model always knows the state.

## Live web pages

With `DNDKIT_WEB_PORT` set, the server also serves web pages that follow
the game as it happens: every change made through a tool, and every roll, is
pushed to the open pages at once (server-sent events). The pages run inside
the MCP server's process, so they are up while roomkit-ui runs the server and
reconnect by themselves when it restarts. A taken port only logs a warning;
the game goes on without the pages.

| Address | For | Shows |
| --- | --- | --- |
| `/table/` | a shared screen (TV, laptop) | The campaign's name and pitch, the session, place and date; initiative order, the party's hit points and conditions (absent players' characters faded), the table with who sits where, the dice tray, active quests, the adventure log, and a QR code per character |
| `/p/<code>/` | each player's phone | Their full character sheet, the fight, the dice, quests and log, the party; "Your turn!" and a buzz when their turn comes |
| `/gm/` | you, on the computer running the game | Everything, to follow and debug what the model does: the **model's activity** (every tool call with its arguments, its answer or error and its time, and the skills the client fetched); the fight with exact monster hit points and AC, or the last fight between two; the adventure log with importance, characters and tags; planned encounters and their difficulty; every quest with its objectives and notes; the notebook (current situation, world notes, setting, past sessions, version, campaign file, last save, skills); the world (NPCs with their secrets and ties, locations with the party's marked, the bestiary's full stat blocks and how many are fighting); every character's full sheet with the game master's notes; the players' join codes |

- **Joining**: players scan their character's code on the table screen. Each
  link carries a code derived from the campaign, the character and a key kept
  in the data directory (`player-links.key`): it cannot be guessed, survives
  restarts, and belongs to the active campaign. Delete the key file to change
  every link.
- **What players see** is built field by field from what they may know: the
  campaign's description (a pitch: `create_campaign` asks for no spoilers), their
  party in full, but a monster only as *unhurt*, *hurt*, *bloodied* or *down*,
  and never an NPC's biography or notes, a planned encounter, a monster's
  statistics or the game master's notes.
- **The activity** lives in memory for the session, like the dice log, and
  skips the widgets' own `get_screen_data` polling. A call the client refuses
  before sending it (roomkit checks required arguments) never reaches the
  server, so it is not there: look at the client's log for those.
- **The backstage** opens at `/gm/` only from the computer running the
  server: a loopback peer, asking for this server by name (`localhost`, its
  address or `DNDKIT_WEB_URL`'s host), so a web page whose domain points at
  this computer (DNS rebinding) is refused. From anywhere else it opens with
  its link, `/gm/<code>/`, written in the server's log at each start. Requests carrying proxy headers are
  refused too, but a reverse proxy or tunnel on that computer that adds none
  would make every visitor look local: do not put one in front of the pages.
- **Read-only**: the pages never change the game; it changes through the
  conversation, so the model always knows the state.
- **Phones** need `DNDKIT_WEB_HOST=0.0.0.0` and the same network. The table
  screen then puts this computer's network address in the codes, even when it
  is open at `127.0.0.1`. For players elsewhere, put a private network such as
  Tailscale between you and set `DNDKIT_WEB_URL`; the pages carry no other
  authentication.
- The log names the addresses at startup: `Table screen: http://127.0.0.1:8765/table/`.

## Data

See [docs/STORAGE_STRUCTURE.md](docs/STORAGE_STRUCTURE.md). Campaigns saved by
gamemaster-mcp, dndkit's upstream, load as they are and are rewritten in the
current format at their first change. Its global `events/adventure_log.json`
is not imported: events now belong to their campaign.

## Development

```bash
uv sync --extra dev
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy src/
uv run bandit -r src/ -c pyproject.toml
npm ci && npx knip     # unused files and exports in the pages' scripts
```

The pages' scripts (`src/dndkit/ui/*.js`) are ES modules, so knip can
follow who imports what; each page inlines them as one script. GitHub Actions
runs all of the above on every push and pull request (Python 3.12 and 3.13),
and `pre-commit install` runs most of it before each commit.

[CLAUDE.md](CLAUDE.md) describes the architecture and the project's rules.

### Releasing

Each change worth telling goes into [CHANGELOG.md](CHANGELOG.md) under
`## Unreleased` with the commit that makes it. To release, on an up-to-date
`main`:

```bash
uv run python scripts/release.py prepare 0.5.0   # versions follow semver
git push origin main v0.5.0
```

`prepare` names the Unreleased section `## 0.5.0 (<date>)`, sets the version
in `pyproject.toml` and `uv.lock`, commits `release: 0.5.0` and tags
`v0.5.0`; it refuses outside `main`, with uncommitted changes, an empty
Unreleased section or an existing tag. The tag runs
`.github/workflows/release.yml`: it checks that the tag matches the version,
sits on `main` and has its changelog section, runs the tests and builds, then
publishes to PyPI by trusted publishing (no token: PyPI trusts the workflow in
its `pypi` environment), pushes the Docker image to `ghcr.io/sboily/dndkit`
(the version, `<major>.<minor>` and `latest`, for amd64 and arm64), and makes
the GitHub release, its notes the version's changelog section, the built files
attached. A failed step stops what follows: nothing reaches GitHub's releases
before PyPI and the registry have the version.

Once, on pypi.org: add a pending trusted publisher for the project `dndkit`
(owner `sboily`, repository `dndkit`, workflow `release.yml`, environment
`pypi`). GitHub creates the `pypi` environment at the first release; required
reviewers set on it (Settings → Environments) hold each release for approval.

## License

MIT, see [LICENSE](LICENSE). dndkit keeps the copyright of gamemaster-mcp,
the project it was forked from.
