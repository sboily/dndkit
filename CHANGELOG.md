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
- Combatants are found by a unique part of their name, as with characters,
  in every tool (`change_hit_points` included).
- The running fight keeps up with the campaign: a combatant named after a
  party character, or holding its name ("Fizbin the gnome"), is linked to the
  sheet, even when the sheet is created after the fight began; a monster that
  joined without numbers takes its stat block once `save_monster` saves it.
  `next_turn`, `save_monster`, `create_character` and the hit point and
  condition tools catch up first and say what changed.
- Casters get their class's spell slots and casting ability at creation;
  sheets give the spell attack bonus, save DC and initiative bonus, and the
  sheet on screen shows background, alignment, appearance, story, spells with
  their descriptions, gear, features, proficiencies and languages.
- The backstage (`/gm/`) becomes the place to debug the model: its activity
  (every tool call with arguments, answer or error and time, recorded by a
  FastMCP middleware; skill listings and reads too), the notebook (situation,
  world notes, setting, past sessions, version, campaign file, last save,
  published skills), every full sheet with the game master's notes, and the
  join codes. All of it stays off the players' screens.
- The backstage shows all the game master holds: the combat card stays up
  between fights with the last one (rounds, who fought, who fell, XP; kept in
  the campaign as `last_combat`), finished encounters (faded), the adventure
  log's last 40 entries with session, importance, characters and tags,
  sessions in full (moments, who was there, XP, treasure, notes), equipped
  items, item type, value and weight, race traits, spell school and
  components, and NPC statistics.
- The backstage (`/gm/`) gains a world section: NPCs (secrets, notes, ties),
  locations (the party's marked, notes) and the bestiary's full stat blocks
  (boss, legendary uses, actions, how many are fighting); quests show their
  objectives. `save_monster` and the monsters skill steer book monsters to
  their book numbers: the challenge-rating table is for invented ones.
- `get_character` without a name reads whose turn it is, or the only
  character. The server instructions tell the model to resolve every roll
  itself and never ask the players for a number the tools hold.
- `remove_combatant` takes a `reason`: `defeated` or `fled` foes count for XP,
  a `withdrawn` one (a mistake, a change of plan) leaves no trace on the
  defeated list or the map. The map skill and the monsters skill say how to
  take a creature back.
- Model parameters lose their docstring in the advertised schemas (the
  parameter's description says it): fewer tokens.

- **Proficiencies**: `update_character` sets skills, saving throws (English
  or French names), languages and features; a new character is proficient in
  its class's saving throws; the sheets give each proficient skill and save
  with its bonus.
- **Hit Dice**: `rest` with `hit_dice` spends them on a short rest (rolled on
  the dice tray); a long rest gives half of them back.
- **Concentration**: `set_concentration`; damage asks for the Constitution
  save, 0 HP or incapacitation ends the spell; the screens show it.
- **Secret rolls**: `roll_dice` with `secret`, shown on the backstage only.
- **Stable** at 0 HP (three successes, or `record_death_save` with
  `stabilized`): no more death saves until hit or healed.
- **Exhaustion** 4 halves the hit point maximum; 6 kills.
- **Reactions**: `take_reaction`, one a round; a creature that has reacted
  provokes no more opportunity attacks.
- **Timed conditions**: `set_condition` with `rounds`, counted down and ended
  by `next_turn`.
- Open pages no longer slow the tools down: each view renders once per change
  for every page showing it, in threads of its own, and a read-only call only
  refreshes the backstage's activity. With 50 pages open, a tool answers in
  2 ms as with none (7 ms before); past 64 connections the server answers 503.
- Two processes on one data directory (two clients, an overlapping restart)
  no longer overwrite each other's changes: changes take turns through
  `<data dir>/.lock`, and the active campaign is read again when its file
  changed elsewhere (a hand edit too). Three processes making 200 changes
  each kept 600; before, 200.
- **CI**: GitHub Actions run ruff, mypy, bandit and the tests on Python 3.12
  and 3.13, and knip on the pages' scripts, now ES modules.

### Changed

- After a roll call, encounter difficulty counts the characters at the table
  only, and `award_experience` without names shares between them (the whole
  party until then).
- The widgets and the web pages share their renderers (`ui/components.js`,
  `ui/dicetray.js`) and words (`ui/words.js`); the JSON views moved from
  `tools/screen_views.py` to the `views` package.
- `CampaignStore` and `DiceLog` take a change callback.
- New dependencies: `starlette` and `uvicorn` (already installed with FastMCP),
  `segno` for the QR codes, `pyyaml` for skill frontmatter; `httpx`,
  `types-pyyaml` and `pytest-cov` for development. Every dependency stops
  before its next major version (`uvx --from git+...` installs without the lock).
- `remove_from_campaign` works in two calls, like `delete_campaign`: the
  first names what would go and gives a code. A removed character leaves the
  running fight.
- `start_combat` with an encounter alone brings the characters at the table,
  initiative rolled and shown on the dice tray.
- `get_campaign_info` gives the setting's first 1,500 characters (`full` for
  the rest); `get_game_state` shows each character's level, and
  `update_game_state` no longer takes a party level nobody kept up.
- `next_turn` tells a down character's turn to roll a death save;
  `save_monster` says when AC and HP come from the challenge rating.
- Campaign names compare without accents, like every other name.
- The views every player may see (dice, party, seats, a sheet) moved from
  `views.widgets` to `views.everyone`, which holds no secret.

### Fixed

- Creating or linking goes by whole names: saving a "Wolf" no longer rewrote
  the "Dire Wolf", a "Wolf" combatant no longer fought on Wolfgang's sheet, and
  "Thorn" hits the character Thorn before the "Thornback Boar".
- A fallen ally no longer counts as a foe overcome (XP); a fight whose last
  combatant was taken out closes with `end_combat`.
- A character created above level 1 gets its level's proficiency bonus and hit
  dice (a level 5 wizard casts at +6, DC 14); `level_up` adds one hit die
  instead of restoring them all; healing no longer raises the dead.
- The backstage refuses DNS rebinding and proxied requests; a hidden foe
  overcome no longer shows on the players' screens.
- A web view that fails no longer cuts the others off; a refused feed is tried
  again instead of claiming to reconnect.
- A bad file in the campaigns folder (dangling link, absurd nesting) no longer
  stops the server; a relative `GAMEMASTER_STORAGE_DIR` is refused instead of
  resolved against the client's working directory; a non-UTF-8 setting file
  or an accented confirmation code is a clear error.
- Old mid-combat saves with odd initiative entries load.
- French class names in the feminine (Magicienne, Guerrière, Rôdeuse...) are
  known: their characters got a d8 and no spell slots.

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
