# Data storage

`CampaignStore` (`src/gamemaster_mcp/storage/store.py`) keeps campaigns as JSON
files in the data directory: `$GAMEMASTER_STORAGE_DIR`, else the per-user data
directory (`~/Library/Application Support/gamemaster-mcp` on macOS,
`~/.local/share/gamemaster-mcp` on Linux, `%LOCALAPPDATA%\gamemaster-mcp` on
Windows).

```
<data dir>/
├── campaigns/
│   ├── Ghost Coast.json
│   └── The Dragons Curse.json
├── settings/
│   └── forgotten-realms.md
└── trash/
    └── Old Campaign 2026-10-11 174223.json
```

## campaigns/

One file per campaign holding the whole `Campaign` model: characters, NPCs,
locations and quests (each a map keyed by entity ID), session notes, the
adventure log (`events`), the game state and world notes.

- **File name**: the campaign name reduced to letters, digits, spaces, `-`
  and `_` ("The Dragon's Curse!" → `The Dragons Curse.json`). Two names that
  reduce to the same file, ignoring case, cannot coexist: `create_campaign`
  refuses the second one instead of overwriting the first.
- **Writes** are atomic: the JSON goes to a hidden `.tmp` file next to the
  target, is flushed to disk, then renamed over it. A crash leaves the old
  file or the new one, never half of one.
- **Startup** opens the most recently opened or changed campaign (by file
  modification time). A file that cannot be read is logged and skipped; it is
  never overwritten.
- **Changes** happen inside `CampaignStore.transaction()`: the campaign is
  saved when the tool succeeds and restored when it fails.

## trash/

`delete_campaign` moves a campaign file here, with the date and time of the
deletion added to its name; nothing is erased. To bring one back, move it into
`campaigns/` and remove the date from its name. Empty the folder by hand.

## settings/

Optional world documents (`.md` or `.txt`, up to 200 KB) for `create_campaign`
and `update_campaign`'s `setting_file`. The text is copied into the campaign,
so editing the file later does not change an existing campaign. Only files
directly in this folder are read; paths and symlinks leading out are refused.

## Files from the upstream server

Upstream saves keyed entities by name and kept one global
`events/adventure_log.json` for every campaign. They load as they are: entities
are re-keyed by ID, unknown keys (`encounters`, `active_quests`,
`current_turn`) are ignored, and the file is rewritten in the current format at
the first change. The global adventure log is not imported, since nothing
records which campaign its events belonged to.
