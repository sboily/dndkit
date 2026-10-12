# A local model as the game master

Does a model running on this machine pick the right tools? This proof of
concept plays scripted table turns through **roomkit 0.98.0**, the way
roomkit-ui does, against gamemaster-mcp, and checks each scenario's calls and
the campaign they leave.

- **Model**: llama.cpp (roomkit's pinned build), by default
  `ornith-ai/Ornith-1.5-35B-A3B-GGUF:Q8_0`, thinking off as roomkit-ui sets it
  for voice.
- **Game master**: an `AIChannel` with the README's system prompt, the
  server's tools over stdio, the skills read from `src/gamemaster_mcp/skills`.
- **Players**: named as roomkit-ui names its voices: Sylvain and Marie are the
  room's participants, each turn carries its speaker (`sender_name`), and the
  prompt ends with roomkit-ui's roster note ("Speaker A is \"Sylvain\", the
  user...").
- **Campaign**: a fresh one per scenario (`scenarios.SEED`): Thrain (Sylvain)
  and Aria (Marie), Mara the innkeeper, a quest, a goblin's stat block.

## Variants

| Variant | Skills | Tool Search | What the model sees |
| --- | --- | --- | --- |
| `auto` | on | roomkit decides | roomkit-ui's defaults: past 20 tools with an unknown window, `find_tools` |
| `skills` | on | off | the tools the skills do not gate, the rest after `activate_skill` |
| `full` | off | off | all 61 tools |

## Scenarios

Seating, asking an NPC, an attack, a spell with its slot, ending a turn, a
short rest with Hit Dice, picking up an item, searching (a roll), moving on
the battle map, preparing a monster, concentration, a shove. Each one's check
is in `scenarios.py`: the calls it needs, and the state they must leave (the
goblin hurt, the slot spent, Thrain next to the goblin...).

## Run

```bash
cd poc/local-model
uv sync
# roomkit starts llama-server (the first run downloads the model):
uv run python run.py
# or reuse a llama-server already running on a port:
uv run python run.py --port 8091 --variants auto,full --only attack,spell --repeat 3
```

Each run writes `results/<time>/calls.jsonl` (every call with its arguments,
result, refusal or error, and the replies) and `summary.md`.
