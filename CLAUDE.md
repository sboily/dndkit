# Gamemaster MCP

FastMCP 4 server (stdio) that keeps a D&D 5e campaign for an AI game master,
made for voice clients such as roomkit-ui.

## Commands

```bash
uv sync --extra dev                  # Environment with dev tools
uv run gamemaster-mcp                # Run the server (stdio)
uv run pytest -q                     # Tests
uv run ruff check . && uv run ruff format --check .
uv run mypy src/                     # Strict
uv run bandit -r src/ -c pyproject.toml
```

## Architecture

```
src/gamemaster_mcp/
├── app.py        # build_server(): FastMCP, lifespan (store + dice log), tools, apps; main()
├── config.py     # Data dir (env, else platformdirs) and stderr logging
├── errors.py     # GameError hierarchy, subclasses of FastMCP's ToolError
├── models/       # Pydantic models: base, character, world, bestiary, campaign
├── storage/      # files (slugs, atomic JSON), catalog (summaries),
│                 # confirmations (one-time codes), store (CampaignStore)
├── game/         # Game logic over a Campaign object: no MCP, no disk
│   ├── registry.py    # Lookup by ID / spoken name / unique part, uniqueness, edits
│   ├── characters.py  # Create/update/remove, hit point changes and the 0 HP rules
│   ├── effects.py     # HP, temporary HP, conditions on characters or combatants
│   ├── resources.py   # Items, death saves, short and long rests
│   ├── spellbook.py   # Spell slots and known spells
│   ├── progression.py # XP awards and level up
│   ├── combat.py      # Initiative order by index, rounds, defeated, summary
│   ├── combatants.py  # Participants -> combatants (linked PCs, bestiary stats)
│   ├── bestiary.py    # Monsters, planned encounters, difficulty
│   ├── world.py       # NPCs, locations, quests, remove_entity
│   ├── journal.py     # Session notes, adventure log
│   ├── dice.py        # Notation parser, roller, in-memory DiceLog
│   ├── rules.py       # HP, XP, levels, slots, encounter difficulty
│   ├── tables.py      # 5e numbers: CR XP, thresholds, slots, hit dice, class aliases
│   └── reference.py   # Short rule reminders, English and French names
├── tools/        # MCP adapters, one module per area, each exporting TOOLS
│   ├── deps.py        # get_store / get_dice_log dependencies, shared annotations
│   ├── schema.py      # Compacts advertised schemas (drops the null alternative)
│   ├── apps.py        # ui:// pages, app_meta(), register_apps()
│   ├── screen.py      # get_screen_data, the widgets' data tool
│   ├── screen_views.py# JSON views for the widgets
│   └── render*.py     # Plain-text views of game data
└── ui/           # MCP App pages: <name>.html + shared.css/shared.js, assembled by ui.page()
```

Layers only call downwards: `tools` → `game` → `models`; `tools` → `storage`.
A tool opens `store.transaction()` (changes) or `store.reading()` (reads),
calls `game` functions on the campaign, and renders a short text answer.

## Rules

- A module well past ~300 lines or a function past ~40 lines is a prompt to
  split by responsibility. A tool's parameter list is its schema and counts
  apart; keep the body short.
- English in code, comments, commits and docs.
- Every new tool goes in its area's `TOOLS` list, gets a test through
  `fastmcp.Client` in `tests/test_tools.py`, and the expected tool count there.

## Gotchas

- **Errors**: raise a `GameError` subclass for anything the model caused or can
  fix. FastMCP sends a `ToolError` message verbatim as an `is_error` result and
  masks every other exception (`mask_error_details=True`). roomkit turns
  `is_error` into `ToolFailedError`; a returned "not found" string would read
  as a success. Say what is known ("Known characters: ...") so the model retries.
- **Transactions**: every change goes through `CampaignStore.transaction()`,
  which restores the campaign if anything raises and saves it otherwise.
  Never mutate the campaign outside one.
- **Threads**: FastMCP runs sync tools in a thread pool and voice models call
  tools in parallel, hence the store's lock. Keep tools synchronous.
- **No import side effects**: the store opens in the lifespan. Importing the
  package must not touch the disk (`test_importing_the_server_touches_no_disk`).
- **Data dir**: MCP clients start the server with no working directory of
  their own (`/` for a macOS app). Never resolve a path against the cwd.
- **Schemas**: roomkit strips `additionalProperties` and Gemini refuses an
  object parameter without `properties`. Use a model (like `Combatant`) for
  structured parameters, never `dict`. Keep descriptions short (see Schema budget).
- **Validators**: models use `validate_assignment`; a validator must never
  assign to `self` (it would recurse). Invariants that old saves may break
  (current HP above max) are enforced in `game/`, not in the models, so those
  saves still load.
- **Legacy saves**: upstream files keyed entities by name and stored a global
  adventure log. `Campaign._key_by_id` re-keys on load; keep
  `tests/fixtures/legacy_campaign.json` loading.
- **Destructive actions**: `delete_campaign` deletes nothing on its first call;
  it issues a one-time code (`storage/confirmations.py`) that a second call
  must carry. A code serves once, for one campaign, for 5 minutes, and a wrong
  one cancels the request. Deleted files go to `trash/`, never unlinked. Reuse
  `Confirmations` for any new destructive tool.
- **MCP Apps in roomkit-ui**: the page receives only the tool's text result
  (no `structuredContent`), one widget per tool name is replaced at each call,
  and the page cannot tell the model anything. So every page reads its data
  with `tools/call get_screen_data` and polls it; pages never change the game
  (the model would not know). Keep pages self-contained (relative URLs 404, and
  sessions may be offline), never `console.error` (roomkit shows it under the
  widget), never pass `null` to `replaceChildren` (it prints "null"; use
  `GM.fill`), and avoid `body { height: 100% }` (it breaks auto-sizing).
  roomkit-ui answers request ids as strings and may miss the first
  `ui/initialize`; `shared.js` handles both. To see a page, render it in
  roomkit-ui's own `MCPAppWidget` with `QT_QPA_PLATFORM=offscreen` and grab it.
- **Schema budget**: `tests/test_tools.py` keeps the catalogue under roomkit's
  Tool Search threshold. `tools/schema.compact` must also walk `$defs`: FastMCP
  inlines model parameters (`Participant`) only after registration.
- **Setting files** are read only from `<data dir>/settings/`, by bare file
  name; symlinks out of it are refused.
