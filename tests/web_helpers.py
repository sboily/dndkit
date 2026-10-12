"""A campaign full of secrets, and the web site over it."""

import json
from pathlib import Path
from typing import Any

from gamemaster_mcp.activity import ActivityLog
from gamemaster_mcp.config import WebSettings
from gamemaster_mcp.game.dice import DiceLog
from gamemaster_mcp.models import (
    NPC,
    Combatant,
    Encounter,
    EncounterGroup,
    Location,
    Monster,
    Quest,
)
from gamemaster_mcp.storage import CampaignStore
from gamemaster_mcp.web.access import PlayerLinks
from gamemaster_mcp.web.audiences import Sources, Views
from gamemaster_mcp.web.changes import Changes
from gamemaster_mcp.web.feed import render_once
from tests.helpers import make_character


def make_sources(tmp_path: Path, settings: WebSettings | None = None) -> Sources:
    """Sources over a fresh campaign (see ``fill_with_secrets``)."""
    changes = Changes()
    store = CampaignStore(tmp_path, on_change=changes.notify)
    store.create("Secrets", "A campaign with things to hide")
    fill_with_secrets(store)
    return Sources(
        store=store,
        dice=DiceLog(on_record=changes.notify),
        changes=changes,
        links=PlayerLinks.open(tmp_path),
        settings=settings or WebSettings(port=0),
        activity=ActivityLog(),
    )


def fill_with_secrets(store: CampaignStore) -> None:
    """Aria fights a bloodied goblin (3/7 HP, AC 15), a hidden scout has fled unseen;
    every private field says SECRET."""
    with store.transaction() as campaign:
        aria = make_character("Aria", hp=12, notes="SECRET-CHARACTER-NOTE")
        campaign.characters[aria.id] = aria
        for entity in (
            NPC(name="Mara", description="An innkeeper", bio="SECRET-BIO", notes="SECRET-NPC"),
            Location(name="Port", location_type="town", description="Wet", notes="SECRET-PLACE"),
            Monster(name="Dragon", armor_class=19, hit_points=256, xp=18000, actions="SECRET-ART"),
            Monster(name="Goblin", armor_class=15, hit_points=7, notes="SECRET-GOBLIN"),
            Encounter(name="SECRET-AMBUSH", monsters=[EncounterGroup(monster="Dragon")]),
        ):
            getattr(campaign, _collection(entity))[entity.id] = entity
        quest = Quest(title="Find the bell", description="Ring it", notes="SECRET-QUEST")
        quest.objectives = ["Reach the tower", "Ring the bell"]
        quest.completed_objectives = ["Reach the tower"]
        campaign.quests[quest.id] = quest
        campaign.world_notes = "SECRET-WORLD"
        state = campaign.game_state
        state.notes = "SECRET-STATE"
        state.in_combat = True
        state.combat_round = 2
        state.initiative_order = [
            Combatant(name="Aria", initiative=15, character_id=aria.id),
            Combatant(
                name="Goblin", initiative=12, hit_points=3, hit_points_max=7, armor_class=15
            ),
        ]
        state.defeated = [Combatant(name="SECRET-SCOUT", initiative=9, xp=700, hidden=True)]


def _collection(entity: object) -> str:
    return {
        NPC: "npcs",
        Location: "locations",
        Monster: "monsters",
        Encounter: "encounters",
    }[type(entity)]


def aria_token(sources: Sources) -> str:
    with sources.store.reading() as campaign:
        aria = next(c for c in campaign.characters.values() if c.name == "Aria")
        return sources.links.token(campaign, aria)


def rendered(views: Views) -> dict[str, Any]:
    """Every view's data, as a page would receive it."""
    return {name: json.loads(text) for name, text in render_once(views).items()}
