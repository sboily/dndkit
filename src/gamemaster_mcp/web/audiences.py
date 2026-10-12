"""The views each audience may stream: the table, one player, the game master.

A feed asks for some views by name and gets only those its audience lists.
"""

from collections.abc import Callable
from dataclasses import dataclass

from gamemaster_mcp.activity import ActivityLog
from gamemaster_mcp.config import WebSettings
from gamemaster_mcp.errors import GameError, NotFoundError
from gamemaster_mcp.game.dice import DiceLog
from gamemaster_mcp.models import Campaign
from gamemaster_mcp.storage import CampaignStore
from gamemaster_mcp.views import desk, everyone, public, widgets
from gamemaster_mcp.views.backstage import backstage
from gamemaster_mcp.views.everyone import Json
from gamemaster_mcp.views.world import world
from gamemaster_mcp.web import access
from gamemaster_mcp.web.access import PlayerLinks
from gamemaster_mcp.web.changes import Changes
from gamemaster_mcp.web.feed import Render

Views = dict[str, Render]
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
    return {
        **_shared(sources),
        "combat": sources.reading(public.combat),
        "join": sources.reading(lambda c: access.join(c, sources.links, phones, reachable)),
    }


def player(sources: Sources, token: str) -> Views:
    """One player's phone: the shared screen's views and that character's sheet."""

    def sheet(campaign: Campaign) -> Json:
        character = sources.links.character_for(campaign, token)
        if character is None:
            raise NotFoundError("unknownLink")  # a word the page translates
        return everyone.character(campaign, character.id)

    return {
        **_shared(sources),
        "combat": sources.reading(public.combat),
        "me": sources.reading(sheet),
    }


def game_master(sources: Sources, base_url: str) -> Views:
    """The backstage: exact numbers, plans, secrets, and what the model does."""
    store = sources.store
    return {
        **table(sources, base_url),  # the join codes too
        "combat": sources.reading(widgets.combat),
        "dice": lambda: everyone.dice(sources.dice, secrets=True),
        "backstage": sources.reading(backstage),
        "world": sources.reading(world),
        "sheets": sources.reading(desk.sheets),
        "notebook": sources.reading(
            lambda c: desk.notebook(c, store.current_file, store.data_dir)
        ),
        "activity": lambda: desk.activity(sources.activity),
        "journal": sources.reading(lambda c: public.journal(c, limit=GM_EVENTS, full=True)),
    }


def _shared(sources: Sources) -> Views:
    return {
        "party": sources.reading(everyone.party),
        "seating": sources.reading(everyone.seating_chart),
        "journal": sources.reading(public.journal),
        "dice": lambda: everyone.dice(sources.dice),
    }
