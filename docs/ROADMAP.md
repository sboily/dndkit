# dndkit 🐉 - Project Roadmap

## 🏰 Vision Statement

The dndkit server aims to be the ultimate AI-assisted Dungeon Master for DnD 5e, providing:

- **For Groups**: A comprehensive toolkit to help human DMs run campaigns more effectively
- **For Solo Players**: A complete virtual DM experience that facilitates immersive solo play
- **For Worldbuilders**: Powerful tools to assist in creating rich, interconnected game worlds

Built on FastMCP, the server provides structured data models and intelligent tools to manage all aspects of a D&D campaign while enabling natural language interaction through MCP clients.

## Current state (0.4.0)

What the server does today is in the [README](../README.md), how it is built in
[CLAUDE.md](../CLAUDE.md), how campaigns are stored in
[STORAGE_STRUCTURE.md](STORAGE_STRUCTURE.md), and what changed from upstream
in the [CHANGELOG](../CHANGELOG.md).

From the roadmap below, done: the advanced combat tools (damage and healing
with `change_hit_points`, conditions, spell slots, legendary actions, a battle
map), rule reminders (`lookup_rule`), a bestiary (`save_monster`,
`get_monsters`), and automated level up (`level_up`). The rest is upstream's
and still open. Closer at hand, for a voice game master: concentration,
spending hit dice on a short rest, skill and saving throw proficiencies set by
the model, condition durations, and secret rolls kept off the players' screens.

---

## 🛣️ Future Development Roadmap

### Phase 1: Enhanced Interactivity & DM Assistance (v1.1)

**Goal**: Move beyond data management to proactive, intelligent assistance that enhances the DM's creative workflow.

| Feature                       | Description                                                                                                                                                           | Related Tools / Models                                                                                             |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| **Data Storage Improvement**  | Migrate from simple JSON data storage to a more robust, efficient system with semantic search features (SQL and/or vector DB such as PostgreSQL, ChromaDB, or Qdrant) | `generate_random_encounter`, `generate_plot_hook`                                                                  |
| **Dynamic Event Generation**  | Tools to generate random encounters, plot hooks, or NPC interactions based on the current `GameState` (e.g., party location, level, active quests).                   | `generate_random_encounter`, `generate_plot_hook`                                                                  |
| **Generative Content Tools**  | Leverage the LLM's `sample` capability to generate descriptions for locations, NPCs, or items on the fly, saving them to the appropriate model.                       | `generate_npc_description`, `generate_location_details`                                                            |
| **Advanced Combat Tools**     | More granular combat management tools for applying damage/healing, adding/removing conditions, and tracking resources (e.g., spell slots, legendary actions).         | `apply_damage`, `add_condition_to_character`, `use_spell_slot`                                                     |
| **Improved Search & Query**   | Enhance the `search_events` tool and add new search capabilities to find specific items, characters, or lore across the entire campaign based on complex queries.     | `find_item_by_property`, `search_lore`                                                                             |
| **Knowledge Base Integration**| Add tools to look up rules, monster stats, or spell details from an integrated (and *user-expandable*) D&D 5e SRD knowledge base.                                          | `lookup_rule`, `get_monster_stats`, `get_spell_details`                                                            |
| **Expanded Character Sheet**  | Add support for tracking feats, skills, and other detailed character attributes beyond the core stats.                                                                | `Feat`, `Skill` models, `add_feat_to_character`                                                                    |
| **Worldbuilding Utilities**   | Tools for procedural generation of names, locations, plot hooks, and other creative elements to assist in worldbuilding.                                              | `generate_random_name`, `generate_location_idea`                                                                   |

### Phase 2: Deeper Simulation & Automation (v1.2)

**Goal**: Automate complex game mechanics and create a more dynamic, simulated world that reacts to player actions.

| Feature                          | Description                                                                                                                                                           | Related Tools / Models                                                                                             |
| -------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| **Faction & Reputation System**  | Introduce `Faction` models and tools to track player reputation with various in-game factions. Reputation changes could be triggered by completing quests or events. | `Faction` model, `update_reputation`, `get_faction_standing`                                                       |
| **Automated Character Progression** | A `level_up_character` tool that automatically handles HP increases, new features, and spell slot changes based on class.                                           | `level_up_character`, `CharacterClass` model updates                                                               |
| **Dynamic World State**          | The `GameState` will evolve more dynamically. NPCs change locations, shop inventories update, and quests become time-sensitive based on in-game date progression.      | `advance_in_game_time`, `update_npc_location`, `restock_shop_inventory`                                            |
| **Loot Generation**              | Tools to generate treasure hoards, magic items, or shop inventories based on challenge rating, location type, or campaign setting.                                     | `generate_treasure_hoard`, `generate_magic_item`                                                                   |
| **Calendar & Time-Based Events** | A more robust in-game calendar system. Schedule world events that trigger automatically when a certain date is reached via the `advance_in_game_time` tool.         | `Calendar` model, `schedule_world_event`                                                                           |

### Phase 3: Scalability & Integration (v1.3)

**Goal**: Evolve the server from a standalone tool into a scalable, interconnected hub for a broader D&D ecosystem.

| Feature                       | Description                                                                                                                                                           | Related Tools / Models                               |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| **Performance Optimization**  | Refactor the storage layer to handle extremely large campaigns with thousands of events and entries without performance degradation.                                    | `CampaignStore` optimization                         |
| **API for Third-Party Apps**  | Expose a secure, public API that allows other applications (e.g., character sheet managers, virtual tabletops) to read and write data to the campaign.                  | `OAuth2` integration, `RESTful API` models           |
| **Webhooks & Event Streaming**| Implement a system for pushing real-time updates to other services when key events occur in the campaign (e.g., a character levels up, a quest is completed).          | `Webhook` model, `emit_event` tool                   |
