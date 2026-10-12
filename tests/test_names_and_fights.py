"""Names that hold other names, and fights that start or end at the edges."""

import pytest
from fastmcp import Client

from gamemaster_mcp.errors import InvalidChangeError, NotFoundError
from gamemaster_mcp.game import bestiary, combat, combatants, effects
from gamemaster_mcp.models import Combatant, Participant
from tests.helpers import call, call_error, make_campaign, make_character

pytestmark = pytest.mark.anyio


def test_a_wolf_is_not_wolfgang_nor_the_dire_wolf() -> None:
    campaign = make_campaign()
    wolfgang = make_character("Wolfgang", hp=20)
    campaign.characters[wolfgang.id] = wolfgang
    bestiary.save_monster(campaign, "Dire Wolf", {"armor_class": 14, "hit_points": 37})
    wolf, created = bestiary.save_monster(campaign, "Wolf", {"armor_class": 13, "hit_points": 11})
    assert created and campaign.monsters[wolf.id].hit_points == 11
    assert bestiary.find_monster(campaign, "Dire Wolf").hit_points == 37
    fighter = combatants.build(campaign, Participant(name="Wolf", initiative=12))
    assert (fighter.character_id, fighter.hit_points) == (None, 11)


def test_a_whole_name_wins_over_part_of_another() -> None:
    campaign = make_campaign()
    thorn = make_character("Thorn", hp=20)
    campaign.characters[thorn.id] = thorn
    boar = Combatant(name="Thornback Boar", initiative=10, hit_points=30, hit_points_max=30)
    combat.start(campaign.game_state, [boar])
    effects.change_hit_points(campaign, ["thorn"], -5)
    assert (thorn.hit_points_current, campaign.game_state.initiative_order[0].hit_points) == (
        15,
        30,
    )
    with pytest.raises(NotFoundError, match="Unknown: 'or'"):  # too short to be a part
        effects.change_hit_points(campaign, ["or"], -1)


def test_a_name_shared_by_several_fighters_hits_no_one() -> None:
    campaign = make_campaign()
    wolfgang = make_character("Wolfgang", hp=20)
    campaign.characters[wolfgang.id] = wolfgang
    wolves = [Combatant(name="Dire Wolf", initiative=i, hit_points=37) for i in (5, 4)]
    combat.start(campaign.game_state, wolves)
    with pytest.raises(NotFoundError, match="Unknown: 'wolf'"):
        effects.change_hit_points(campaign, ["wolf"], -6)
    assert wolfgang.hit_points_current == 20


def test_one_target_named_twice_is_hit_once() -> None:
    campaign = make_campaign()
    combat.start(campaign.game_state, [Combatant(name="Goblin", initiative=5, hit_points=7)])
    effects.change_hit_points(campaign, ["Goblin", "goblin"], -3)
    assert campaign.game_state.initiative_order[0].hit_points == 4


def test_a_part_of_a_name_links_a_character_by_whole_words() -> None:
    campaign = make_campaign()
    aria = make_character("Aria Moonwhisper")
    campaign.characters[aria.id] = aria
    linked = combatants.build(campaign, Participant(name="Aria", initiative=3))
    assert linked.character_id == aria.id
    with pytest.raises(InvalidChangeError, match="Given twice"):
        combat.start(
            campaign.game_state,
            [
                linked,
                combatants.build(campaign, Participant(name="aria moonwhisper", initiative=9)),
            ],
        )


def test_numbered_foes_skip_a_number_already_given() -> None:
    goblins = [Combatant(name=n, initiative=5) for n in ("Goblin", "Goblin", "Goblin 1")]
    names = [c.name for c in combatants.number_duplicates(goblins)]
    assert names == ["Goblin 2", "Goblin 3", "Goblin 1"]


def test_a_fallen_ally_is_no_foe_overcome() -> None:
    state = make_campaign().game_state
    guard = Combatant(name="Guard", initiative=12, xp=25, ally=True)
    orc = Combatant(name="Orc", initiative=8, xp=100)
    combat.start(state, [guard, orc])
    combat.remove(state, "Guard")
    combat.remove(state, "Orc")
    assert combat.end(state).xp == 100


def test_a_fight_emptied_by_hand_still_closes() -> None:
    state = make_campaign().game_state
    combat.start(state, [Combatant(name="Goblin", initiative=5)])
    combat.remove(state, "Goblin", overcome=False)
    with pytest.raises(InvalidChangeError, match="end_combat first"):
        combat.start(state, [Combatant(name="Orc", initiative=5)])
    assert combat.end(state).xp == 0 and state.combat_round == 0
    with pytest.raises(InvalidChangeError, match="No combat is running"):
        combat.end(state)


async def test_a_fight_started_with_its_foes_only_brings_the_party(client: Client) -> None:
    await call(client, "create_campaign", name="Cave", description="d")
    await call(
        client, "create_character", name="Aria", character_class="Wizard", race="Elf", dexterity=14
    )
    await call(client, "save_monster", name="Goblin", challenge_rating="1/4")
    await call(client, "plan_encounter", name="Cave", monsters=[{"monster": "Goblin", "count": 2}])
    started = await call(client, "start_combat", encounter="Cave")
    assert "Initiative rolled for the party: Aria " in started
    assert "Aria" in started.split("party:")[1] and "Goblin 2" in started
    rolls = await call(client, "get_screen_data", view="dice")
    assert "d20+2" in rolls
    refused = await call_error(client, "save_monster", name="Gob", boss=True)
    assert "give its full name: Goblin" in refused
