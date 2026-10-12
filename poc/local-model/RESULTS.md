# Results: Ornith 1.5 35B-A3B (Q8_0), 2026-10-12

llama.cpp b11160 on an Apple M5 Max (128 GB), roomkit 0.98.0, temperature 0.7,
12 scenarios × 3 variants × 2 attempts per series. A scenario passes when the
calls it needs were made and the campaign holds the result (see
`scenarios.py`). The map move check was corrected after the runs (Thrain, a
dwarf, cannot reach a goblin 35 ft away without a Dash: moving 25 ft toward it
is right); the totals below count it that way.

## Passed scenarios

| Thinking | auto (Tool Search) | skills | full (61 tools) |
| --- | --- | --- | --- |
| off (roomkit-ui's setting for llama.cpp) | 6/24 | 10/24 | 5/24 |
| on | 10/24 | **19/24** | **18/24** |

## Seconds per scenario (one or two spoken turns, every tool round included)

| Thinking | auto | skills | full |
| --- | --- | --- | --- |
| off | median 3.7, p90 17 | median 3.3, p90 13 | median 2.8, p90 9 |
| on | median 24, p90 64 | median 18, p90 44 | median 17, p90 35 |

## What the runs show

- **Thinking decides whether the tools get used.** Without it the model
  narrates instead of acting: 9 of 24 turns without a single call with the
  skills, 15 of 24 with the whole catalogue (the dagger "goes into the bag",
  Mara answers from imagination). With it, every turn but one calls tools.
- **Tool Search hurts.** roomkit-ui's default (`auto`) turns it on for a model
  whose window roomkit does not know. It is the worst variant both ways: the
  model loops on `find_tools`, invents skills (`dnd-magic`, `dnd-dungeon`), and
  piles up refused calls (171 in the thinking series, 98 in one turn).
- **Skills or the whole catalogue: the same with thinking (19 vs 18), skills
  twice as good without it.** Merging tools is not needed for this model.
- **Names get translated**: "Goblin" for "Gobelin", retried up to five times
  although the error lists the known names; invented characters ("Ragnar",
  "Kael"); a name passed as "> Thrain".
- **The roll call is forgotten**: `seat_players` at the start of a session in
  1 run of 6, even with thinking: the model greets, reads the campaign, plays on.
- **Thinking costs time**: about 18 s per scenario against 3 s, long for a
  spoken turn.

## Limits of this run

Two attempts per cell: a difference of one or two scenarios is noise. roomkit
labels each turn with its speaker only once two people have spoken, so the
one-line scenarios leave the model to guess who talks. The server's MCP
instructions never reach the model (roomkit RMK-692): only the README prompt
does.
