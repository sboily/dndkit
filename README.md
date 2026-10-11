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
  file. Creating a campaign never overwrites an existing one.
- **Characters**: full 5e sheets, damage and healing with temporary hit points
  applied first, inventory that stacks, spell slots, death saves, long rests.
- **World**: NPCs (with private bios), locations and quests with numbered objectives.
- **Combat**: initiative order tracked by position, so three "Goblin"s become
  "Goblin 1/2/3" and each gets its turn; round counter; removing the fallen.
- **Journal**: session notes and a per-campaign adventure log with search.
- **Dice**: `d20`, `1d20+5`, `2d6+1d4+3`, advantage and disadvantage.

Names are matched without case or accents ("elodie" finds "Élodie"), the way a
speech transcript spells them. When a call fails, the error says why and lists
the known names, so the model can correct itself instead of guessing.

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
| Environment variables | `GAMEMASTER_STORAGE_DIR=/Users/you/Games/dnd` (optional) |

From a local checkout instead: Command `uv`, Arguments
`run --directory /path/to/gamemaster-mcp gamemaster-mcp`.

The 41 tool schemas weigh about 7,000 tokens, under the point where roomkit
hides tools behind `find_tools`. Put the system prompt below in the assistant's
personality.

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

The Gamemaster tools hold the campaign. Trust them over your memory:
- Before describing a character, place or quest, read it (get_character,
  get_location, get_quest, get_game_state).
- Record every change as it happens: damage and healing with
  bulk_update_characters, items with add_item_to_character and
  remove_item_from_character, spell slots with use_spell_slot, the party's
  location and date with update_game_state.
- Roll every die with roll_dice and say the result; never invent a roll.
- In combat, start_combat with everyone's initiative, then next_turn after each
  turn and remove_combatant when someone falls or flees.
- Log notable moments with add_event, and summarise the session with
  add_session_note when the players stop.
- When a tool reports an unknown name, pick the right one from the names it
  lists, or ask the players; never create a duplicate.
- Ask before removing anything with remove_from_campaign.

Starting a new campaign, run a short session zero, one question at a time:
the campaign's name and pitch, then each player's character (name, race,
class, level, hit points, ability scores), the starting location, a first NPC
and a first quest, creating each with its tool as soon as you have it.
```

## Tools

| Area | Tools |
| --- | --- |
| Campaign | `create_campaign`, `get_campaign_info`, `list_campaigns`, `load_campaign`, `update_campaign`, `remove_from_campaign` |
| Characters | `create_character`, `get_character`, `list_characters`, `update_character`, `bulk_update_characters` |
| Resources | `add_item_to_character`, `remove_item_from_character`, `set_spell_slots`, `use_spell_slot`, `record_death_save`, `long_rest` |
| NPCs | `create_npc`, `get_npc`, `update_npc`, `list_npcs` |
| Locations | `create_location`, `get_location`, `update_location`, `list_locations` |
| Quests | `create_quest`, `get_quest`, `update_quest`, `list_quests` |
| Table | `get_game_state`, `update_game_state`, `start_combat`, `next_turn`, `remove_combatant`, `end_combat` |
| Journal | `add_session_note`, `get_sessions`, `add_event`, `get_events` |
| Utility | `roll_dice`, `calculate_experience` |

`update_character` sets absolute values; `bulk_update_characters` applies
relative changes (damage, healing, ability score changes) to one or more
characters, and changes nobody if one name is unknown. A tool that fails
changes nothing, in memory or on disk.

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
