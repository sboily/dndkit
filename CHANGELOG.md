# Changelog

## 0.2.0 (fork)

First release of the fork, rebuilt on FastMCP 4 for voice game masters
(roomkit-ui) and to fix the upstream 0.1 server.

### Fixed

- `update_character`, `add_item_to_character` and `bulk_update_characters`
  failed on every call: the lookup by ID returned nothing. Characters are
  found by ID or by name again.
- A failed tool call no longer leaves half-applied changes that the next save
  would write: every change runs in a transaction restored on failure.
- `create_campaign` no longer overwrites an existing campaign of the same name;
  creating a character, NPC, location or quest under a taken name is refused
  instead of replacing the first one.
- The server starts when the client gives it no working directory (`/` for a
  macOS app): data goes to `$GAMEMASTER_STORAGE_DIR` or the per-user data
  directory, never the current directory.
- Every log line no longer prints a "Logging error" traceback (broken
  `GameStatHandler`, removed with the unused `GameStats`).
- `next_turn` no longer loops between combatants who share a name; turns are
  tracked by position, duplicates numbered, rounds counted.
- `update_character` applies ability scores instead of silently ignoring them,
  and refuses current HP above the maximum.
- `roll_dice` accepts `d20`, keeps the modifier in `1d20 + 5`, refuses `0d6`,
  `1d0`, `1d20abc` and huge rolls, and treats advantage plus disadvantage as a
  normal roll.
- `calculate_experience` splits the monsters' XP evenly; the DMG difficulty
  multipliers no longer change the XP awarded.
- Damage takes temporary hit points first; damage at 0 HP counts as a failed
  death save.
- `add_event` no longer answers `<built-in method lower ...>`.
- `create_campaign`'s setting path was never read; `setting_file` now reads a
  file from the data directory's `settings/` folder, and nothing outside it.
- `get_game_state` counts active quests from the quests themselves.
- Campaign files are written atomically.
- The adventure log belongs to its campaign instead of being shared by all.

### Added

- `delete_campaign`, confirmed in two calls: the first returns what would be
  lost and a one-time code (5 minutes); the second, with the code, moves the
  campaign file to `<data dir>/trash/`.
- `list_campaigns` gives each campaign's pitch, size, session and last use,
  most recent first.
- Tools: `update_campaign`, `remove_from_campaign`, `update_npc`,
  `update_location`, `get_quest`, `remove_item_from_character`,
  `set_spell_slots`, `use_spell_slot`, `record_death_save`, `long_rest`,
  `remove_combatant`.
- Names match without case or accents; errors list the known names.
- Failures reach the client as MCP errors (`is_error`), with a message meant
  for the model.
- `get_character` shows inventory, spell slots, skills, features and notes.

### Changed

- FastMCP 4.1 (MCP SDK 2.x). The 853-line `main.py` is split into `models/`,
  `storage/`, `game/` and `tools/` modules.
- Tool answers are short plain text, without emoji, for voice models.
- `start_combat` takes typed participants (`name`, `initiative`); `roll_dice`
  takes `notation` (was `dice_notation`); `create_character` defaults to
  level 1 and takes `hit_points_max` and `armor_class`.
- `calculate_experience` drops the unused `party_level`; `update_game_state`
  drops `in_combat` (use `start_combat`/`end_combat`).
- Configuration through environment variables only; `.env` loading and
  `python-dotenv` are gone.
- Tests run through `fastmcp.Client`; ruff, strict mypy and bandit are clean.

### Removed

- `requirements.txt` (use `uv.lock`), `mypy.ini` (in `pyproject.toml`), the
  vendored FastMCP 2.9 docs, `docs/DEVELOPMENT.md` (see `CLAUDE.md`), the Roo
  logs and the empty example folder.
- The unused `CombatEncounter` model.
