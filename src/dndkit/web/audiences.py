"""The views each audience may stream: the table, one player, the game master.

A feed asks for some views by name and gets only those its audience lists.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from dndkit.activity import ActivityLog
from dndkit.config import WebSettings
from dndkit.errors import GameError, NotFoundError
from dndkit.game.dice import DiceLog
from dndkit.models import Campaign
from dndkit.storage import CampaignStore
from dndkit.views import desk, everyone, public, widgets
from dndkit.views.backstage import backstage
from dndkit.views.everyone import Json
from dndkit.views.world import world
from dndkit.web import access
from dndkit.web.access import PlayerLinks
from dndkit.web.changes import ACTIVITY, Changes
from dndkit.web.feed import Render, Renders, View

Views = dict[str, View]
GM_EVENTS = 40  # of the adventure log, on the backstage


@dataclass(frozen=True)
class Sources:
    """What the web pages read, all shared with the MCP tools."""

    store: CampaignStore
    dice: DiceLog
    changes: Changes
    links: PlayerLinks
    settings: WebSettings
    activity: ActivityLog
    renders: Renders = field(default_factory=Renders)

    def reading(self, build: Callable[[Campaign], Json]) -> Render:
        """A render of the active campaign through *build*."""

        def render() -> Json:
            with self.store.reading() as campaign:
                return build(campaign)

        return render

    def player(self, token: str) -> str | None:
        """The name of the character whose link carries *token*, if any."""
        try:
            with self.store.reading() as campaign:
                character = self.links.character_for(campaign, token)
        except GameError:  # no active campaign
            return None
        return character.name if character else None


def table(sources: Sources, base_url: str) -> Views:
    """The shared screen: what everyone at the table may see, and the join codes."""
    phones, reachable = access.phone_base_url(sources.settings, base_url)
    join = sources.reading(lambda c: access.join(c, sources.links, phones, reachable))
    return {
        **_shared(sources),
        "join": View(join, f"join@{phones}"),  # the links follow the address asked
    }


def player(sources: Sources, token: str) -> Views:
    """One player's phone: the shared screen's views and that character's sheet."""

    def sheet(campaign: Campaign) -> Json:
        character = sources.links.character_for(campaign, token)
        if character is None:
            raise NotFoundError("unknownLink")  # a word the page translates
        return everyone.character(campaign, character.id)

    return {**_shared(sources), "me": View(sources.reading(sheet), f"me@{token}")}


def game_master(sources: Sources, base_url: str) -> Views:
    """The backstage: exact numbers, plans, secrets, and what the model does."""
    store = sources.store
    renders: dict[str, Render] = {
        "combat": sources.reading(widgets.combat),
        "dice": lambda: everyone.dice(sources.dice, secrets=True),
        "backstage": sources.reading(backstage),
        "world": sources.reading(world),
        "sheets": sources.reading(desk.sheets),
        "notebook": sources.reading(
            lambda c: desk.notebook(c, store.current_file, store.data_dir)
        ),
        "journal": sources.reading(lambda c: public.journal(c, limit=GM_EVENTS, full=True)),
    }
    return {
        **table(sources, base_url),  # the join codes too
        **{name: View(render, f"gm/{name}") for name, render in renders.items()},
        "activity": View(lambda: desk.activity(sources.activity), "gm/activity", ACTIVITY),
    }


def _shared(sources: Sources) -> Views:
    """What the table and every phone show alike: rendered once for all of them."""
    renders: dict[str, Render] = {
        "party": sources.reading(everyone.party),
        "seating": sources.reading(everyone.seating_chart),
        "journal": sources.reading(public.journal),
        "dice": lambda: everyone.dice(sources.dice),
        "combat": sources.reading(public.combat),
    }
    return {name: View(render, f"public/{name}") for name, render in renders.items()}
