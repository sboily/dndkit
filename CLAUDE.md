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
├── app.py        # build_server(): FastMCP + lifespan that opens the store; main()
├── config.py     # Data dir (env, else platformdirs) and stderr logging
├── errors.py     # GameError hierarchy, subclasses of FastMCP's ToolError
├── models/       # Pydantic models: base (GameModel), character, world, campaign
├── storage/      # files.py (slugs, atomic JSON), store.py (CampaignStore)
├── game/         # Game logic over a Campaign object: no MCP, no disk
│   ├── registry.py   # Lookup by ID or spoken name, uniqueness, validated edits
│   ├── characters.py # Create/update/remove, relative HP and score changes
│   ├── resources.py  # Items, spell slots, death saves, long rest
│   ├── world.py      # NPCs, locations, quests, remove_entity
│   ├── combat.py     # Initiative order by index, rounds
│   ├── journal.py    # Session notes, adventure log
│   ├── dice.py       # Notation parser and roller
│   └── rules.py      # HP change with temporary HP, XP split
└── tools/        # MCP adapters, one module per area, each exporting TOOLS
    ├── deps.py       # get_store dependency, shared annotations
    └── render.py     # Plain-text views of game data
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
  structured parameters, never `dict`. Keep descriptions short: the catalogue
  must stay under roomkit's Tool Search threshold (~8,000 tokens, tested).
- **Validators**: models use `validate_assignment`; a validator must never
  assign to `self` (it would recurse). Invariants that old saves may break
  (current HP above max) are enforced in `game/`, not in the models, so those
  saves still load.
- **Legacy saves**: upstream files keyed entities by name and stored a global
  adventure log. `Campaign._key_by_id` re-keys on load; keep
  `tests/fixtures/legacy_campaign.json` loading.
- **Setting files** are read only from `<data dir>/settings/`, by bare file
  name; symlinks out of it are refused.
