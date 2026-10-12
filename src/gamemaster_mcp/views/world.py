"""The world as the game master knows it: NPCs, places and the bestiary, secrets included."""

from gamemaster_mcp.models import NPC, Campaign, Location, Monster
from gamemaster_mcp.text import normalize
from gamemaster_mcp.views.everyone import Json


def world(campaign: Campaign) -> Json:
    """Every NPC, location and stat block, by name."""
    here = normalize(campaign.game_state.current_location or "")
    fighting = [c.monster for c in campaign.game_state.initiative_order if c.monster]
    return {
        "npcs": [_npc(n) for n in sorted(campaign.npcs.values(), key=lambda n: n.name)],
        "locations": [
            _location(place, normalize(place.name) == here)
            for place in sorted(campaign.locations.values(), key=lambda p: p.name)
        ],
        "monsters": [
            _monster(m, fighting.count(m.name))
            for m in sorted(campaign.monsters.values(), key=lambda m: m.name)
        ],
    }


def _npc(npc: NPC) -> Json:
    return {
        "name": npc.name,
        "race": npc.race,
        "occupation": npc.occupation,
        "location": npc.location,
        "attitude": npc.attitude,
        "description": npc.description,
        "bio": npc.bio,
        "notes": npc.notes,
        "ties": [f"{who}: {what}" for who, what in npc.relationships.items()],
        "stats": [f"{key}: {value}" for key, value in (npc.stats or {}).items()],
    }


def _location(place: Location, current: bool) -> Json:
    return {
        "name": place.name,
        "type": place.location_type,
        "current": current,
        "description": place.description,
        "population": place.population,
        "government": place.government,
        "features": place.notable_features,
        "npcs": place.npcs,
        "connections": place.connections,
        "notes": place.notes,
    }


def _monster(monster: Monster, fighting: int) -> Json:
    return {
        "name": monster.name,
        "size": monster.size,
        "ac": monster.armor_class,
        "hp": monster.hit_points,
        "speed": monster.speed,
        "cr": monster.challenge_rating,
        "xp": monster.xp,
        "initiative": monster.initiative_bonus,
        "boss": monster.boss,
        "legendary": [monster.legendary_actions, monster.legendary_resistances],
        "actions": monster.actions,
        "notes": monster.notes,
        "fighting": fighting,
    }
