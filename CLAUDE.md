# dndkit

FastMCP 4 server (stdio) that keeps a D&D 5e campaign for an AI game master,
made for voice clients such as roomkit-ui.

## Commands

```bash
uv sync --extra dev                  # Environment with dev tools
uv run dndkit                        # Run the server (stdio)
uv run pytest -q                     # Tests
uv run ruff check . && uv run ruff format --check .
uv run mypy src/                     # Strict
uv run bandit -r src/ -c pyproject.toml
npm ci && npx knip                   # Unused files and exports in ui/*.js
DNDKIT_WEB_PORT=8765 uv run dndkit   # Also serve the web pages
DNDKIT_TRANSPORT=http uv run dndkit  # MCP over HTTP at :8000/mcp (Docker's way)
```

CI (`.github/workflows/ci.yml`) runs all of these on every push, Python 3.12
and 3.13; its actions are pinned by commit. Note each user-visible change
under `## Unreleased` in CHANGELOG.md. `scripts/release.py prepare <version>`
on main stamps the changelog, sets the version, commits and tags; pushing the
tag runs `release.yml` (PyPI by trusted publishing, then the GitHub release
with the changelog section).

The project was gamemaster-mcp before its rename (a fork of
study-flamingo/gamemaster-mcp): `config.py` still reads the `GAMEMASTER_*`
variables and the old data directory; everything new says dndkit.

## Architecture

```
src/dndkit/
├── app.py        # build_server(): FastMCP, lifespan (store, dice log, web pages), tools, apps
├── activity.py   # In-memory log of the model's calls, for the backstage
├── config.py     # Data dir (env, else platformdirs), stderr logging, WebSettings, HttpSettings
├── transport.py  # MCP over HTTP: the bearer token, /health
├── errors.py     # GameError hierarchy, subclasses of FastMCP's ToolError
├── text.py       # normalize(): how two spellings of a name compare, for every layer
├── models/       # Pydantic models: base, character, world, bestiary, battle, campaign
├── storage/      # files (slugs, atomic JSON), catalog (summaries),
│                 # confirmations (one-time codes), store (CampaignStore)
├── game/         # Game logic over a Campaign object: no MCP, no disk
│   ├── registry.py    # Lookup by ID / spoken name / unique part, uniqueness, edits
│   ├── characters.py  # Create/update/remove, hit point changes and the 0 HP rules
│   ├── effects.py     # HP, temporary HP, conditions on characters or combatants
│   ├── resources.py   # Items, death saves, short and long rests
│   ├── spellbook.py   # Spell slots and known spells
│   ├── progression.py # XP awards (to those at the table) and level up
│   ├── seating.py     # Who plays which character, the roll call, who is present
│   ├── combat.py      # Initiative order by index, rounds, defeated, summary
│   ├── grid.py        # Squares "D7", areas, footprints by size, distances
│   ├── battlefield.py # The map: terrain, who stands where, placement at the edges
│   ├── pathing.py     # Routes for one mover (Dijkstra), opportunity attacks
│   ├── movement.py    # Speed, standing up, Dash/Disengage, to/toward/away, forced
│   ├── sight.py       # Lines across the map: line of effect, cover, check_target facts
│   ├── areas.py       # Spheres, cubes, cones, lines: squares and who is caught
│   ├── combatants.py  # Participants -> combatants (linked PCs, bestiary stats)
│   ├── bestiary.py    # Monsters, planned encounters, difficulty
│   ├── readiness.py   # What a campaign lacks before play (check_campaign)
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
│   ├── recorder.py    # Middleware writing every tool call and skill read to the activity
│   ├── screen.py      # get_screen_data, the widgets' data tool
│   └── render*.py     # Plain-text views of game data (render_map: the map in text)
├── views/        # JSON views for screens. What players may see, field by field:
│                 # everyone (dice, party, seats, a sheet), public (the fight,
│                 # the journal). GM only: widgets (the fight in full), backstage
│                 # (plans), world (NPCs, places, bestiary), desk (activity,
│                 # notebook, full sheets). battle: the map, for both
├── web/          # Live web pages, inside the MCP process: changes (notices from
│                 # tool threads), access (player links, QR), audiences (views
│                 # per page), feed (SSE), routes (Starlette), server (uvicorn)
├── skills/       # Agent Skills (<name>/SKILL.md) and their publication over MCP:
│                 # catalog (frontmatter, files, digests), extension (SEP-2640:
│                 # skill:// resources, skills/list, skills/get)
└── ui/           # Pages: widgets and web pages (<name>.html), shared.css,
                  # components.css, words.js, shared.js (transports), dicetray.js,
                  # battlemap.js, backstage.js, world.js, desk.js, sheet.js, components.js,
                  # assembled by ui.page()
```

Layers only call downwards: `tools` → `game` → `models`; `tools` → `storage`;
`tools` and `web` → `views` → `game`. `storage` and `game.dice` report changes
through plain callbacks and know nothing of the web.
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
  Never mutate the campaign outside one. Another process may share the data
  dir (`storage/sharing.py`): a transaction holds `<data dir>/.lock` and both
  it and `reading()` reread the active file when its stamp changed. A new
  way to write a campaign file must hold the lock and update `_stamp`.
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
- **Web pages**: they run in the MCP server's process, on its event loop. stdout
  is the MCP protocol and Ctrl-C belongs to the MCP server, hence uvicorn with
  `log_config=None` and no signal capture, and a socket bound by us (uvicorn
  exits the process when it cannot bind). Nothing on the web side may stop the
  game. A new way for `CampaignStore` to change the game must call
  `self._on_change()`, or the pages stay stale. Each streamed view is a
  `feed.View` with a key (feeds showing the same thing share its text, so a
  view rendered for the table renders once for every phone; a view that
  depends on the request, like the join links, puts it in its key) and a
  topic: `GAME` (store, dice) or `ACTIVITY` (the model's calls, which change
  nothing else). Pages render in their own small thread pool, never the tools'.
- **Player views** (`views/everyone.py`, `views/public.py`) list every field
  they send; never pass a model or a GM view through, and never put a secret
  in them (the GM views add theirs on top). `tests/test_web_views.py` fills
  every private field with `SECRET` and checks the table and player feeds. The
  backstage is local-only by peer address and by Host (DNS rebinding), and
  refuses proxied requests: keep `proxy_headers=False`.
- **Page scripts are ES modules** (`import`/`export`, for knip) that
  `ui.page()` inlines as one classic script: it drops the import lines and the
  `export` keywords, so a module's top-level names stay global, and keeps
  `ui.SCRIPTS` order (a module after those it imports; a test checks it). Keep
  imports on one line, `import { A, B } from "./x.js";`, and export only
  top-level `const`/`function`/`class` declarations.
- **Pages share renderers**: a widget and a web page show the same
  `Views.*` component; only the transport differs (`window.GM_WEB` set by the
  server: one EventSource per page, since browsers allow few connections per
  host). Style a component under its root class (`.combat`, `.party`...): a web
  page shows several at once.
- **Players**: roomkit-ui names the voices and opens each spoken turn with the
  speaker's name; the server keeps no speaker IDs, only names (a character's
  `player_name`, and `GameState.players_present` for the roll call), compared
  with `seating.same_person`. Anything that should count only the characters
  at the table (difficulty, XP) goes through `seating.present_characters`,
  which is the whole party until a roll call.
- **Debugging the model**: open `/gm/` (needs `DNDKIT_WEB_PORT`). The
  activity there shows each tool call as the model made it and what it got
  back, failures in red; `tools/recorder.py` records them and leaves out
  `get_screen_data`. A new protocol method (like `skills/list`) records itself.
- **A fight that drifts**: combatants copy what they need when they join, so
  a sheet created or a stat block saved later would not reach them.
  `combatants.refresh` links and fills them; call it from any tool that acts
  on the fight (the effects, `next_turn`, `save_monster`, `create_character`)
  and report its lines.
- **Battle map**: squares are names ("D7"), stored as text (`Battlefield`,
  `Combatant.position`, the top-left square of a big creature) and parsed
  with `grid.parse` against the map. Movement follows the PHB grid rule
  (diagonals 5 ft); `pathing` is the only place that knows what blocks or
  provokes, and `movement` the only place that spends movement. Moves that
  break a rule raise `InvalidChangeError` (the model then offers Dash or
  `toward`), except `toward`, which goes as far as it can. Movement resets in
  `combat._begin_turn`. The players' map (`views.battle`, `public=True`) has
  no hit points for foes and shows reachable squares on the party's turns only.
- **Hidden foes**: `views.battle.unseen` says what the players must not see.
  Every public view drops those foes (order, tokens, the party banner's
  current turn), and the reachable squares are computed as if they were not
  there (`Ground(as_players_see=True)`). A new public view must do the same.
- **Input models**: a tool takes a small model for structured input (`Layout`,
  `Placement`, `Seat`) and never a stored model, whose internal fields would
  be advertised (`Battlefield.area`). `schema.compact` drops a model's
  docstring from the schema: put the words in the parameter's description.
- **Skills**: a skill's `allowed_tools` hides those tools from roomkit's
  catalogue until the skill is activated. A tool must still work without the
  skill (other clients have none): never rely on the skill's text. Skills are
  published by SEP-2640: a folder's name must be its frontmatter `name`, the
  listing's frontmatter is the file's verbatim, and digests are of the bytes
  served (text is read back exactly as stored). A skill file that is not
  Markdown needs `pyproject.toml`'s package data widened. `tests/test_tools.py`
  counts the budget with the gates; `tests/test_skills.py` checks the
  extension end to end.
- **Schema budget**: `tests/test_tools.py` keeps the catalogue under roomkit's
  Tool Search threshold. `tools/schema.compact` must also walk `$defs`: FastMCP
  inlines model parameters (`Participant`) only after registration.
- **HTTP and Docker**: stdio stays the default. Over HTTP (`transport.py`)
  the lifespan runs once for every client, so they share one store, as
  several stdio processes share the data dir. A token is required beyond
  loopback; `/health` is the only route without it. Behind Docker every peer
  is the gateway, so the backstage opens with its link (`/gm/<code>/`, from
  the same secret as the players' links); never loosen `_local` for Docker.
  No Docker here: CI's `docker` job builds the image and tries it.
- **Setting files** are read only from `<data dir>/settings/`, by bare file
  name; symlinks out of it are refused.
