# Gamemaster MCP

A [Model Context Protocol](https://modelcontextprotocol.io) server that keeps a
Dungeons & Dragons 5e campaign for an AI game master: characters, NPCs,
locations, quests, combat turns, dice, session notes and an adventure log.
It is built with [FastMCP](https://gofastmcp.com) 4 and made for **voice play**,
for example as an MCP service in [roomkit-ui](https://github.com/roomkit-live/roomkit-ui),
while working just as well from Claude Desktop or any MCP client.

This is a fork of [study-flamingo/gamemaster-mcp](https://github.com/study-flamingo/gamemaster-mcp).
See [CHANGELOG.md](CHANGELOG.md) for what changed.

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
- **On-screen widgets** (MCP Apps): rolling dice, a live combat tracker, a party
  board and character sheets, in clients that show MCP Apps.

Names are matched without case or accents ("elodie" finds "Élodie"), and a part
of a name is enough when only one name contains it ("phare" finds "Le phare
éteint"), the way a speech transcript spells them. When a call fails, the error
says why and lists the known names, so the model can correct itself.

## Install and run

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
# Straight from GitHub, no checkout
uvx --from git+https://github.com/sboily/gamemaster-mcp gamemaster-mcp

# From a checkout
git clone https://github.com/sboily/gamemaster-mcp.git
cd gamemaster-mcp
uv sync
uv run gamemaster-mcp
```

The server speaks MCP over stdio: an MCP client starts it, you don't keep it running yourself.

### Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `GAMEMASTER_STORAGE_DIR` | the per-user data directory (below) | Where campaigns are stored |
| `GAMEMASTER_LOG_LEVEL` | `INFO` | Log level; logs go to stderr |
| `GAMEMASTER_WEB_PORT` | unset: no web pages | Serve the [live web pages](#live-web-pages) on this port |
| `GAMEMASTER_WEB_HOST` | `127.0.0.1` | `0.0.0.0` lets phones on the same network open them |
| `GAMEMASTER_WEB_URL` | guessed | The address phones should use, when the server cannot tell (a DNS name, Tailscale) |

Default data directory:

- macOS: `~/Library/Application Support/gamemaster-mcp`
- Linux: `~/.local/share/gamemaster-mcp` (or `$XDG_DATA_HOME/gamemaster-mcp`)
- Windows: `%LOCALAPPDATA%\gamemaster-mcp`

To start a campaign from a prepared world document, drop a `.md` or `.txt` file
in the `settings/` folder of the data directory and pass its name as
`setting_file` to `create_campaign` or `update_campaign`. Only files directly in
that folder can be read.

### With roomkit-ui

In **Settings → Integrations → MCP**, add a server:

| Field | Value |
| --- | --- |
| Name | `Gamemaster` |
| Transport | `stdio` |
| Command | `uvx` |
| Arguments | `--from git+https://github.com/sboily/gamemaster-mcp gamemaster-mcp` |
| Environment variables | `GAMEMASTER_STORAGE_DIR=/Users/you/Games/dnd` (optional)<br>`GAMEMASTER_WEB_PORT=8765` and `GAMEMASTER_WEB_HOST=0.0.0.0` for the web pages (optional) |

From a local checkout instead: Command `uv`, Arguments
`run --directory /path/to/gamemaster-mcp gamemaster-mcp`.

The 56 tool schemas weigh about 7,600 tokens by roomkit's own estimate, under
the 8,000 at which roomkit hides tools behind `find_tools` by default;
optional parameters are advertised without their `null` alternative to stay
there. Put the system prompt below in the assistant's personality.

#### Skills

`skills/` holds Agent Skills for roomkit-ui (Settings → Skills: add this
repository, or its local checkout, as a source, then enable them):

- `dnd-battle-map` teaches the game master to run a fight on the map, and
  gates `set_battlefield`, `place_tokens` and `move_token`: roomkit keeps them
  out of the catalogue (and out of its token count) until the model activates
  the skill.

### With Claude Desktop

```json
{
  "mcpServers": {
    "gamemaster": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/sboily/gamemaster-mcp", "gamemaster-mcp"],
      "env": { "GAMEMASTER_STORAGE_DIR": "/Users/you/Games/dnd" }
    }
  }
}
```

## System prompt for a voice game master

```markdown
You are the game master of a Dungeons & Dragons 5e session played by voice.
Speak the players' language, in short spoken sentences: no lists, no markdown.

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

The Gamemaster tools hold the campaign. Trust them over your memory:
- Before describing a character, place or quest, read it (get_character,
  get_location, get_quest, get_game_state).
- Record every change as it happens: damage and healing with change_hit_points
  (characters and monsters), conditions with set_condition, items with
  add_item_to_character and remove_item_from_character, spells with
  use_spell_slot, the party's location and date with update_game_state.
- Roll every die with roll_dice and say the result; never invent a roll.
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
- Ask before removing anything with remove_from_campaign. To delete a
  campaign, call delete_campaign, tell the players what would be lost, and call
  it again with the code only after a clear yes.

Starting a new campaign, run a short session zero, one question at a time:
the campaign's name and pitch, then each player's character (name, race,
class, level, hit points, ability scores), the starting location, a first NPC
and a first quest, creating each with its tool as soon as you have it.
```

## Tools

| Area | Tools |
| --- | --- |
| Campaign | `create_campaign`, `get_campaign_info`, `list_campaigns`, `load_campaign`, `update_campaign`, `delete_campaign`, `remove_from_campaign` |
| Characters | `create_character`, `get_character` 🖥, `list_characters`, `update_character` |
| Resources | `add_item_to_character`, `remove_item_from_character`, `record_death_save`, `rest` |
| Spells | `set_spell_slots`, `use_spell_slot`, `set_known_spell` |
| Progression | `award_experience`, `level_up` |
| NPCs | `create_npc`, `get_npc`, `update_npc`, `list_npcs` |
| Locations | `create_location`, `get_location`, `update_location`, `list_locations` |
| Quests | `create_quest`, `get_quest`, `update_quest`, `list_quests` |
| Table | `seat_players` 🖥, `get_game_state` 🖥, `update_game_state`, `change_hit_points`, `set_condition` |
| Combat | `start_combat` 🖥, `add_combatant`, `next_turn`, `remove_combatant`, `end_combat` |
| Battle map | `set_battlefield` 🖥, `place_tokens`, `move_token` |
| Bestiary | `save_monster`, `get_monsters`, `plan_encounter`, `list_encounters` |
| Journal | `add_session_note`, `get_sessions`, `add_event`, `get_events` |
| Utility | `roll_dice` 🖥, `lookup_rule`, `get_screen_data` (for the widgets) |

🖥 opens an on-screen widget in clients that support MCP Apps.

`update_character` sets absolute values; `change_hit_points` applies damage or
healing to characters and monsters alike, and changes nobody if one name is
unknown. A tool that fails changes nothing, in memory or on disk.

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

Five tools carry an MCP App (`_meta.ui.resourceUri`): the client opens their
page next to the conversation.

| Tool | Widget |
| --- | --- |
| `roll_dice` | Dice tray: each die tumbles and lands on its face; a natural 20 glows, a natural 1 shakes; with advantage the discarded d20 fades out; recent rolls below. |
| `start_combat` | Combat tracker, live: the battle map when there is one, initiative order, current turn, hit point bars that flash on damage or healing, AC, conditions, the defeated and their XP. |
| `get_game_state` | Party board, live: location, date, funds, every character's hit points, spell slots, conditions and death saves, quest progress, combat banner. |
| `seat_players` | The table, live: the players seated around it with their characters, newcomers without one yet, absent players and characters nobody plays. |
| `get_character` | Character sheet, live: hit points, AC, proficiency, XP to next level, abilities, conditions, spell slots, spells, inventory. |

Each page is self-contained (no network access), French or English after the
system language, and reads its data with the `get_screen_data` tool, refreshing
every couple of seconds: the combat tracker follows `change_hit_points` or
`next_turn` calls made later in the conversation. The widgets only display; the
game changes through the conversation, so the model always knows the state.

roomkit-ui shows MCP Apps since its `MCPManager.read_resource` passes the
resource URI as a string (with the `mcp` 2.x SDK, an `AnyUrl` fails validation
and the widget falls back to a text line).

## Live web pages

With `GAMEMASTER_WEB_PORT` set, the server also serves web pages that follow
the game as it happens: every change made through a tool, and every roll, is
pushed to the open pages at once (server-sent events). The pages run inside
the MCP server's process, so they are up while roomkit-ui runs the server and
reconnect by themselves when it restarts. A taken port only logs a warning;
the game goes on without the pages.

| Address | For | Shows |
| --- | --- | --- |
| `/table/` | a shared screen (TV, laptop) | The campaign's name and pitch, the session, place and date; initiative order, the party's hit points and conditions (absent players' characters faded), the table with who sits where, the dice tray, active quests, the adventure log, and a QR code per character |
| `/p/<code>/` | each player's phone | Their full character sheet, the fight, the dice, quests and log, the party; "Your turn!" and a buzz when their turn comes |
| `/gm/` | you, on the computer running the game | Everything, to follow what the model does: exact monster hit points and AC, planned encounters and their difficulty, NPC secrets and notes, every quest, the bestiary |

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
- **The backstage** opens only from the computer running the server (a
  loopback peer). A reverse proxy or tunnel running on that computer would make
  every visitor look local: do not put one in front of the pages.
- **Read-only**: the pages never change the game; it changes through the
  conversation, so the model always knows the state.
- **Phones** need `GAMEMASTER_WEB_HOST=0.0.0.0` and the same network. The table
  screen then puts this computer's network address in the codes, even when it
  is open at `127.0.0.1`. For players elsewhere, put a private network such as
  Tailscale between you and set `GAMEMASTER_WEB_URL`; the pages carry no other
  authentication.
- The log names the addresses at startup: `Table screen: http://127.0.0.1:8765/table/`.

## Data

See [docs/STORAGE_STRUCTURE.md](docs/STORAGE_STRUCTURE.md). Campaigns saved by
the upstream server load as they are and are rewritten in the current format at
their first change. The upstream global `events/adventure_log.json` is not
imported: events now belong to their campaign.

## Development

```bash
uv sync --extra dev
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy src/
uv run bandit -r src/ -c pyproject.toml
```

[CLAUDE.md](CLAUDE.md) describes the architecture and the project's rules.

## License

MIT, see [LICENSE](LICENSE).
