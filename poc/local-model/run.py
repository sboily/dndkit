"""A local model plays the game master: scripted table turns, every tool call checked.

roomkit 0.98.0 drives the model as roomkit-ui does (an AIChannel, the README's
game master prompt, speaker names, the skills read from their folders, Tool
Search by roomkit-ui's settings) against gamemaster-mcp over stdio, one fresh
campaign per scenario.

    uv run python run.py --port 8091          # a llama-server already serving
    uv run python run.py --model REPO:QUANT   # roomkit starts llama-server itself
    uv run python run.py --variants auto --only attack,spell --repeat 3

Writes results/<time>/calls.jsonl (every turn, every call) and summary.md.
"""

import argparse
import asyncio
import json
import os
import re
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from roomkit import (
    ChannelCategory,
    ChannelType,
    EventSource,
    EventStatus,
    HookExecution,
    HookResult,
    HookTrigger,
    InboundMessage,
    RoomEvent,
    RoomKit,
    SkillRegistry,
    TextContent,
    ToolCallEvent,
    WebSocketChannel,
)
from roomkit.channels.ai import AIChannel
from roomkit.providers.llamacpp import LlamaCppAIProvider, LlamaCppConfig
from roomkit.tools import MCPToolProvider
from scenarios import SCENARIOS, SEED, Call, Scenario

REPO = Path(__file__).resolve().parents[2]
SKILLS = REPO / "src" / "gamemaster_mcp" / "skills"
RESULTS = Path(__file__).resolve().parent / "results"
TURN_TIMEOUT_S = 300


@dataclass(frozen=True)
class Variant:
    """How the tools reach the model."""

    name: str
    skills: bool  # gated tools hidden until their skill is activated
    tool_search: bool | None  # None: roomkit decides (on for a local model past 20 tools)


VARIANTS = {
    "auto": Variant("auto", skills=True, tool_search=None),  # roomkit-ui's defaults
    "skills": Variant("skills", skills=True, tool_search=False),
    "full": Variant("full", skills=False, tool_search=False),
}


@dataclass
class Outcome:
    scenario: str
    variant: str
    attempt: int
    passed: bool
    problems: list[str]
    calls: list[Call]
    replies: list[str]
    seconds: float
    errors: int = field(init=False)

    def __post_init__(self) -> None:
        self.errors = sum(1 for c in self.calls if c["error"])


def game_master_prompt() -> str:
    """The README's system prompt for a voice game master, as users paste it, then
    the note roomkit-ui adds once two voices are named (speaker_roster.prompt_note)."""
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    section = readme.split("## System prompt for a voice game master", 1)[1]
    prompt = re.search(r"```markdown\n(.*?)```", section, re.DOTALL).group(1).strip()
    return f"{prompt}\n\n{ROSTER_NOTE}"


# roomkit-ui's note when its diarizing STT has two named voices, the first the user's.
ROSTER_NOTE = (
    "Several people speak in this conversation; each of their turns opens with who "
    'said it.\n- Speaker A is "Sylvain", the user.\n- Speaker B is "Marie".'
)


class KeptOpen(LlamaCppAIProvider):
    """The model for every scenario. Each scenario's room closes its channels, and
    with them their provider: this one stays open until ``shutdown``. With *shared*,
    a llama-server already running is used, never started nor stopped."""

    def __init__(self, config: LlamaCppConfig, shared: bool) -> None:
        super().__init__(config)
        self._shared = shared

    async def start(self) -> None:
        if not self._shared:
            await super().start()

    async def close(self) -> None:
        return None

    async def shutdown(self) -> None:
        if self._shared:
            await super(LlamaCppAIProvider, self).close()  # the HTTP client only
        else:
            await super().close()  # the client and llama-server


def make_provider(args: argparse.Namespace) -> KeptOpen:
    config = LlamaCppConfig(
        model=args.model,
        context_size=args.context,
        port=args.port,
        enable_thinking=args.thinking,  # roomkit-ui turns it off for voice
        # As roomkit-ui caps a turn: thinking spends the cap before the reply, so a
        # model that thinks gets the whole window (llama-server stops at its end).
        max_tokens=args.context if args.thinking else 1024,
    )
    return KeptOpen(config, shared=args.port is not None)


async def play(
    provider: LlamaCppAIProvider, variant: Variant, scenario: Scenario, attempt: int
) -> Outcome:
    """One scenario on a fresh campaign; the calls, the replies, the verdict."""
    with tempfile.TemporaryDirectory() as data:
        env = {
            "PATH": os.environ["PATH"],
            "HOME": os.environ["HOME"],
            "GAMEMASTER_STORAGE_DIR": data,
        }
        mcp = MCPToolProvider.from_command(
            "uv", ["run", "--directory", str(REPO), "gamemaster-mcp"], env=env
        )
        async with mcp:
            for tool, arguments in scenario.seed if scenario.fresh else [*SEED, *scenario.seed]:
                answer = await mcp.call_tool(tool, arguments)
                if answer.startswith('{"error"'):
                    raise RuntimeError(f"seed {tool} failed: {answer}")
            calls: list[Call] = []
            replies: list[str] = []
            kit = await table(provider, variant, mcp, calls, replies)
            await other_player_spoke(kit, scenario)
            started = time.perf_counter()
            for speaker, text in scenario.turns:
                message = InboundMessage(
                    channel_id="table",
                    sender_id=speaker.lower(),
                    content=TextContent(body=text),
                    metadata={"sender_name": speaker},
                )
                result = await asyncio.wait_for(kit.process_inbound(message), TURN_TIMEOUT_S)
                if result.error is not None:
                    replies.append(f"[turn failed: {result.error}]")
            seconds = time.perf_counter() - started
            await asyncio.sleep(0.3)  # the ASYNC recorder's last calls
            calls.sort(key=lambda c: c["at"])
            state = await read_state(mcp)
            await kit.close()
    problems = scenario.check(calls, state)
    return Outcome(
        scenario.name, variant.name, attempt, not problems, problems, calls, replies, seconds
    )


async def table(
    provider: LlamaCppAIProvider,
    variant: Variant,
    mcp: MCPToolProvider,
    calls: list[Call],
    replies: list[str],
) -> RoomKit:
    """A room with the players' channel and the game master, as roomkit-ui sets it."""
    kit = RoomKit()
    players = WebSocketChannel("table")
    skills = SkillRegistry() if variant.skills else None
    if skills is not None:
        skills.discover(SKILLS)
    gm = AIChannel(
        "gm",
        provider=provider,
        system_prompt=game_master_prompt(),
        tools=mcp.get_tools(),
        tool_handler=mcp.as_tool_handler(),
        skills=skills,
        tool_search=variant.tool_search,
        tool_timeout_seconds=None,
    )
    kit.register_channel(players)
    kit.register_channel(gm)

    # ASYNC: refused calls (bad arguments, a gated tool) reach observers only.
    @kit.hook(HookTrigger.ON_TOOL_CALL, execution=HookExecution.ASYNC, name="record")
    async def record(event: ToolCallEvent, _ctx: Any) -> HookResult:
        if event.result is not None:
            body = event.result if isinstance(event.result, str) else json.dumps(event.result)
            calls.append(
                {
                    "name": event.name,
                    "arguments": event.arguments,
                    "error": event.is_error,
                    "refused": getattr(event, "refused", False),
                    "at": time.perf_counter(),
                    "result": body[:400],
                }
            )
        return HookResult.allow()

    async def heard(_conn: str, event: RoomEvent) -> None:
        if event.source.channel_id == "gm" and isinstance(event.content, TextContent):
            replies.append(event.content.body)

    players.register_connection("speaker", heard, room_id="table")
    await kit.create_room(room_id="table")
    await kit.attach_channel("table", "table")
    for player in PLAYERS:  # the named voices, as the room's participants
        await kit.ensure_participant("table", "table", player.lower(), display_name=player)
    await kit.attach_channel("table", "gm", category=ChannelCategory.INTELLIGENCE)
    return kit


PLAYERS = ("Sylvain", "Marie")


async def other_player_spoke(kit: RoomKit, scenario: Scenario) -> None:
    """A line from the other player, already in the room's history: roomkit labels
    each turn with its speaker once two people have spoken (RFC §6.4), as at a real
    table. Stored, not sent, so the model does not answer it."""
    speakers = {speaker for speaker, _ in scenario.turns}
    if len(speakers) > 1:
        return
    other = next(p for p in PLAYERS if p not in speakers)
    event = RoomEvent(
        room_id="table",
        source=EventSource(channel_id="table", channel_type=ChannelType.WEBSOCKET),
        content=TextContent(body="On y va !"),
        status=EventStatus.DELIVERED,
        metadata={"sender_name": other},
    )
    await kit.store.add_event_auto_index("table", event)


async def read_state(mcp: MCPToolProvider) -> dict[str, Any]:
    """What the checks look at, read straight from the server."""

    async def view(which: str, **extra: str) -> Any:
        return json.loads(await mcp.call_tool("get_screen_data", {"view": which, **extra}))

    return {
        "combat": await view("combat"),
        "party": await view("party"),
        "seating": await view("seating"),
        "sheets": {name: await view("character", name=name) for name in ("Thrain", "Aria")},
        "check": await mcp.call_tool("check_campaign", {}),
    }


def summary(outcomes: list[Outcome]) -> str:
    variants = list(dict.fromkeys(o.variant for o in outcomes))
    names = list(dict.fromkeys(o.scenario for o in outcomes))
    lines = ["| Scenario | " + " | ".join(variants) + " |", "|---" * (len(variants) + 1) + "|"]
    for name in names:
        cells = []
        for variant in variants:
            runs = [o for o in outcomes if o.scenario == name and o.variant == variant]
            passed = sum(o.passed for o in runs)
            calls = sum(len(o.calls) for o in runs) / max(1, len(runs))
            errors = sum(o.errors for o in runs)
            seconds = sum(o.seconds for o in runs) / max(1, len(runs))
            spoken = sum(sum(len(r) for r in o.replies) for o in runs) / max(1, len(runs))
            cells.append(
                f"{passed}/{len(runs)} · {calls:.1f} calls · {errors} err · "
                f"{seconds:.0f}s · {spoken:.0f} chars"
            )
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    totals = []
    for variant in variants:
        runs = [o for o in outcomes if o.variant == variant]
        totals.append(f"**{sum(o.passed for o in runs)}/{len(runs)}**")
    lines.append("| **total** | " + " | ".join(totals) + " |")
    return "\n".join(lines)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--model", default="ornith-ai/Ornith-1.5-35B-A3B-GGUF:Q8_0")
    parser.add_argument("--port", type=int, help="a llama-server already serving the model")
    parser.add_argument("--context", type=int, default=65536)
    parser.add_argument("--thinking", action="store_true", help="let the model think first")
    parser.add_argument("--variants", default="auto,skills,full")
    parser.add_argument("--only", default="", help="scenario names, comma separated")
    parser.add_argument("--repeat", type=int, default=1)
    return parser.parse_args()


def show(outcome: Outcome) -> None:
    """One line per run: the verdict, the time, the calls (! when refused or failed)."""
    mark = "PASS" if outcome.passed else "FAIL"
    names = ", ".join(c["name"] + ("!" if c["error"] else "") for c in outcome.calls)
    print(f"{mark} {outcome.variant:6} {outcome.scenario:15} {outcome.seconds:5.0f}s  {names}")
    for problem in outcome.problems:
        print(f"       - {problem}")


async def main() -> None:
    args = arguments()
    wanted = set(filter(None, args.only.split(",")))
    scenarios = [s for s in SCENARIOS if not wanted or s.name in wanted]
    variants = [VARIANTS[v] for v in args.variants.split(",")]
    runs = [(a, v, s) for a in range(1, args.repeat + 1) for v in variants for s in scenarios]
    out = RESULTS / time.strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True)
    provider = make_provider(args)
    outcomes: list[Outcome] = []
    try:
        await provider.start()
        with (out / "calls.jsonl").open("w", encoding="utf-8") as log:
            for attempt, variant, scenario in runs:
                outcome = await play(provider, variant, scenario, attempt)
                outcomes.append(outcome)
                log.write(json.dumps(asdict(outcome), ensure_ascii=False) + "\n")
                log.flush()
                show(outcome)
    finally:
        await provider.shutdown()
    header = f"# {args.model}\n\nthinking={args.thinking}, context={args.context}\n\n"
    (out / "summary.md").write_text(header + summary(outcomes) + "\n", encoding="utf-8")
    print("\n" + summary(outcomes) + f"\n\n{out}")


if __name__ == "__main__":
    asyncio.run(main())
