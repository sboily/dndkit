# Changelog

## 0.4.0

Live web pages: a table screen, each player's phone, the game master's backstage.

### Added

- **Web pages** (`GAMEMASTER_WEB_PORT`, `GAMEMASTER_WEB_HOST`,
  `GAMEMASTER_WEB_URL`), served from the MCP server's process and updated at
  every change through server-sent events:
  - Every page opens on the campaign's name and pitch (its description, now
    advertised to the model as shown to the players), session, place and date.
  - `/table/`: initiative order, the party, the dice tray, active quests with
    their objectives, the adventure log, and a QR code per character.
  - `/p/<code>/`: one player's character sheet with the fight, the dice, quests
    and log; "Your turn!" and a vibration when their turn comes.
  - `/gm/`, from the computer running the game only: exact monster numbers,
    planned encounters and their difficulty, NPC secrets and notes, every
    quest, the bestiary.
- Players' links are unguessable codes derived from `player-links.key` in the
  data directory. Players never see NPC secrets, notes, planned encounters or
  monster statistics; a monster shows as unhurt, hurt, bloodied or down.

- **Who plays**: `seat_players` (with a widget, the table drawn round) records
  who is at the table tonight and which character each plays, from the names
  roomkit-ui gives the voices. `get_game_state` says it; the server
  instructions and the README's game master prompt open each session with a
  roll call. Party cards show each character's player, absent ones faded.
- The table also shows on the web pages (`/table/`, `/gm/`).
- **Battle map**: `set_battlefield`, `place_tokens` and `move_token` play a
  fight on a grid of 5-foot squares (A1 top left) by the 5e rules: speed,
  difficult terrain, walls, creature sizes, passing allies but not foes,
  standing up from prone, conditions that stop movement, exhaustion, Dash,
  Disengage, opportunity attacks, forced movement, and refusing what cannot
  be done. The combat widget and the web pages draw the map, with the
  squares the acting character can still reach; players see foes' state,
  not their hit points. Characters have a `speed` (from their race unless
  given) and monsters a `size`.
- On the map: `area_of_effect` (spheres, cubes, cones, lines; walls stop
  them; who is caught, shown until the next turn), `check_target` (distance,
  reach, cover by the DMG corner rule, disadvantage from an adjacent foe or a
  hidden target), hidden foes kept off the players' screens until revealed,
  and encounters planned with their map and their monsters' squares.
- **Skills over MCP**: the server publishes its Agent Skills by the official
  MCP Skills extension (SEP-2640, `io.modelcontextprotocol/skills`): the
  capability, `skill://` resources, and `skills/list` and `skills/get` with
  SHA-256 digests. The server instructions point at them.
- `dnd-battle-map` teaches the map and gates its five tools; `dnd-monsters`
  teaches inventing monsters and bosses sized to the party and running
  legendary actions, and gates `save_monster` and `plan_encounter`. With both
  on, roomkit's catalogue weighs about 6,650 tokens.
- **Bosses**: `save_monster` takes `boss`, `legendary_actions` and
  `legendary_resistances` (a boss gets 3 and 3 unless told); `use_legendary`
  spends them in combat, actions coming back at the start of the boss's turn.
  The screens crown the boss; the game master's show what it has left.
- `save_monster` with only a challenge rating fills armor class, hit points
  and attack, damage and save DC guidance from the DMG table; the server
  instructions tell the model to invent the monsters its story needs.
- `create_character` without hit points or armor class uses the PHB's: hit
  die and Constitution by level, 10 + Dexterity.
- Combatants are found by a unique part of their name, as with characters.
- `remove_combatant` takes a `reason`: `defeated` or `fled` foes count for XP,
  a `withdrawn` one (a mistake, a change of plan) leaves no trace on the
  defeated list or the map. The map skill and the monsters skill say how to
  take a creature back.
- Model parameters lose their docstring in the advertised schemas (the
  parameter's description says it): fewer tokens.

### Changed

- After a roll call, encounter difficulty counts the characters at the table
  only, and `award_experience` without names shares between them (the whole
  party until then).
- The widgets and the web pages share their renderers (`ui/components.js`,
  `ui/dicetray.js`) and words (`ui/words.js`); the JSON views moved from
  `tools/screen_views.py` to the `views` package.
- `CampaignStore` and `DiceLog` take a change callback.
- New dependencies: `starlette` and `uvicorn` (already installed with FastMCP),
  `segno` for the QR codes, `pyyaml` for skill frontmatter; `httpx` and
  `types-pyyaml` for development.

## 0.3.0

Monsters with hit points, the missing 5e rules, and on-screen widgets.

### Added

- **Monster hit points in combat.** Combatants carry hit points, AC and
  conditions; party characters stay linked to their sheet. `change_hit_points`
  damages or heals characters and monsters alike; a monster at 0 HP leaves the
  initiative order, and `end_combat` lists the defeated and their total XP.
  `add_combatant` brings newcomers into a running fight without moving the turn.
- **Bestiary and encounters**: `save_monster` / `get_monsters` keep stat blocks
  (XP from the challenge rating); `plan_encounter` / `list_encounters` prepare
  fights rated easy to deadly against the party with the DMG multipliers;
  `start_combat(encounter=...)` runs one, rolling the monsters' initiative.
- **Conditions and exhaustion**: `set_condition` for characters and monsters;
  dropping to 0 HP makes a character unconscious and prone; damage left over
  past 0 HP that reaches the hit point maximum kills outright; a long rest
  removes one exhaustion level.
- **Experience and levels**: `award_experience` splits XP and says who can level
  up; `level_up` adds hit points (hit die roll or average, plus Constitution),
  proficiency, hit dice and the class's spell slots (full, half and pact
  casters; French class names understood).
- **Spells**: `set_known_spell` adds, changes or forgets a spell.
- **Rules**: `lookup_rule` gives short reminders of conditions and core rules,
  by English or French name.
- **Rests**: `rest(kind="short"|"long")` replaces `long_rest`; a short rest gives
  warlocks their pact slots back.
- **On-screen widgets (MCP Apps)**: `roll_dice` (rolling dice), `start_combat`
  (live combat tracker), `get_game_state` (party board) and `get_character`
  (character sheet) open self-contained pages that read `get_screen_data`.
- A part of a name finds an entity when no other name contains it.

### Changed

- `bulk_update_characters` is replaced by `change_hit_points`, and
  `calculate_experience` by `award_experience`.
- Optional parameters are advertised without their `null` alternative: 52 tools
  now cost about as many schema tokens as 42 did.
- `start_combat` takes participants with optional `hit_points` and
  `armor_class`, and/or an `encounter`.
- The FastMCP startup banner is off.

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
