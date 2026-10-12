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

# Second series: answers that say the next step, labelled turns

Same model and settings, thinking on, `skills` and `full`, 3 attempts. The
server now hints the closest name in every not-found error, says how to add a
missing monster, and reminds the roll call; each scenario opens with the
other player's line already in the room, so roomkit labels every turn with
its speaker, as at a real table.

| | skills | full |
| --- | --- | --- |
| all scenarios | 22/36 | 26/36 |
| without seating and the map move | 22/30 (73%; 16/20 before) | 26/30 (87%; 17/20 before) |
| seating, reminder reworded | 1/6 together | |
| map move, asked plainly ("as far as he can") | 2/3 | 3/3 |

- **The name hints work.** With "Did you mean 'Gobelin'?" in the error, the
  model fixes the call on its very next try 11 times out of 12 (8 of 19
  without); name errors fall from 0.40 to 0.26 a run. Names were rarely what
  failed a scenario, so the total barely moves.
- **The roll call is still skipped** (1/6): the model reads "Nobody is seated
  yet. As soon as a player says who they are, call seat_players...", greets,
  reads the campaign, and plays on. Little is lost meanwhile: until a roll
  call, the server counts the whole party as present.
- **"Thrain fonce sur le gobelin" is ambiguous**: with labelled turns the model
  asks whether he dashes instead of moving, a fair game master's question; the
  plain wording passes 5 of 6.
- Turns took longer (median 45 s against 18 s) with the same model and
  settings; with a background agent answering the table, latency is not the
  measure here.

# Third series: the players named as roomkit-ui names them

Same model and settings as the second series, with the plain map wording.
Sylvain and Marie are now the room's participants and the prompt ends with
roomkit-ui's roster note ("Speaker A is \"Sylvain\", the user. Speaker B is
\"Marie\"."): until then the model only saw labelled turns, never who was at
the table.

| | skills | full |
| --- | --- | --- |
| all scenarios | **26/36** (22 before) | **30/36** (26 before) |
| seating | 3/3 (0/3) | 2/3 (0/3) |
| map move, plain wording | 0/3 (2/3) | 3/3 (3/3) |
| the other ten | 23/30 (22/30) | 25/30 (26/30) |

- **Naming the players fixes the roll call**: `seat_players` with the right
  seats in 5 runs of 6, against 1 of 6 with the reminder reworded alone. The
  model greets each player by name and seats them as they speak. The other
  scenarios do not move (23 and 25 of 30 against 22 and 26: noise).
- **The bench's output cap cost some runs.** 4 runs ended without a word (5
  and 6 in the earlier series), all failed: the llama-server log shows 34
  generations stopped at exactly 1024 tokens, the cap set here as roomkit
  sets it. Thinking spends it before the reply. roomkit-ui now lifts the cap
  to the context window when the model thinks.
- **What still fails** (16 runs): the model narrates instead of calling in 7
  (Detect Magic without `set_concentration` 4 times, the battle map move
  without `move_token` twice, the turn handed over without `next_turn`); it
  opens the session again and forgets the owlbear twice; it plays the
  goblin's turn itself, or rolls damage and never applies it (attack, twice);
  it says "je vous installe" and calls nothing (seating, once).
- With skills, the tools a skill gates are the weak spot: the map move and the
  owlbear pass 0 of 6 behind `dnd-battle-map` and `dnd-monsters` (two of those
  six cut by the cap), 5 of 6 with every tool in sight.
