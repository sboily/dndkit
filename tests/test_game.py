"""Game logic on a Campaign object, without MCP or disk."""

import pytest

from gamemaster_mcp.errors import AlreadyExistsError, InvalidChangeError, NotFoundError
from gamemaster_mcp.game import characters, combat, registry, resources, world
from gamemaster_mcp.models import NPC, Combatant, Item, Quest
from tests.helpers import make_campaign, make_character


def test_names_match_without_case_or_accents() -> None:
    campaign = make_campaign()
    characters.create(campaign, make_character("Élodie"))
    assert characters.find(campaign, "elodie").name == "Élodie"
    assert characters.find(campaign, "  ÉLODIE ").name == "Élodie"


def test_lookup_by_id_works() -> None:
    campaign = make_campaign()
    aria = characters.create(campaign, make_character("Aria"))
    assert characters.find(campaign, aria.id) is aria


def test_unknown_name_lists_known_ones() -> None:
    campaign = make_campaign()
    characters.create(campaign, make_character("Aria"))
    with pytest.raises(NotFoundError, match="Known characters: Aria"):
        characters.find(campaign, "Arya")


def test_duplicate_names_are_refused() -> None:
    campaign = make_campaign()
    world.create_npc(campaign, NPC(name="Bob", bio="secret"))
    with pytest.raises(AlreadyExistsError):
        world.create_npc(campaign, NPC(name="bob"))
    assert world.find_npc(campaign, "Bob").bio == "secret"


def test_update_sets_abilities_level_and_rename() -> None:
    campaign = make_campaign()
    characters.create(campaign, make_character("Aria"))
    updated = characters.update(
        campaign, "Aria", {"name": "Aria Moon", "class_level": 3}, {"strength": 18}
    )
    assert updated.abilities["strength"].score == 18
    assert updated.character_class.level == 3
    assert characters.find(campaign, "aria moon") is updated


def test_update_refuses_current_hp_above_max() -> None:
    campaign = make_campaign()
    characters.create(campaign, make_character("Aria", hp=10))
    with pytest.raises(InvalidChangeError, match="cannot exceed"):
        characters.update(campaign, "Aria", {"hit_points_current": 50}, {})


def test_lowering_max_hp_lowers_current_hp() -> None:
    campaign = make_campaign()
    characters.create(campaign, make_character("Aria", hp=10))
    assert characters.update(campaign, "Aria", {"hit_points_max": 6}, {}).hit_points_current == 6


def test_adjust_checks_every_name_before_changing_anyone() -> None:
    campaign = make_campaign()
    aria = characters.create(campaign, make_character("Aria", hp=10))
    with pytest.raises(NotFoundError, match="'Arya'"):
        characters.adjust(campaign, ["Aria", "Arya"], hp_change=-5)
    assert aria.hit_points_current == 10


def test_damage_at_zero_hp_adds_a_death_save_failure() -> None:
    campaign = make_campaign()
    aria = characters.create(campaign, make_character("Aria", hp=5))
    characters.adjust(campaign, ["Aria"], hp_change=-5)
    characters.adjust(campaign, ["Aria"], hp_change=-1)
    assert aria.death_saves_failure == 1
    characters.adjust(campaign, ["Aria"], hp_change=3)
    assert (aria.hit_points_current, aria.death_saves_failure) == (3, 0)


def test_death_saves_follow_the_rules() -> None:
    campaign = make_campaign()
    characters.create(campaign, make_character("Aria", hp=5, hit_points_current=0))
    assert "1 successes" in resources.record_death_save(campaign, "Aria", "success")
    assert "dies" not in resources.record_death_save(campaign, "Aria", "nat1")
    assert "dies" in resources.record_death_save(campaign, "Aria", "failure")
    with pytest.raises(InvalidChangeError, match="dead"):
        resources.record_death_save(campaign, "Aria", "success")


def test_items_stack_and_are_removed() -> None:
    campaign = make_campaign()
    aria = characters.create(campaign, make_character("Aria"))
    resources.add_item(campaign, "Aria", Item(name="Potion", quantity=2, item_type="consumable"))
    resources.add_item(campaign, "Aria", Item(name="potion", item_type="consumable"))
    assert [(i.name, i.quantity) for i in aria.inventory] == [("Potion", 3)]
    with pytest.raises(InvalidChangeError, match="only 3"):
        resources.remove_item(campaign, "Aria", "Potion", 5)
    resources.remove_item(campaign, "Aria", "Potion", 3)
    assert aria.inventory == []


def test_spell_slots_are_spent_and_restored_by_a_long_rest() -> None:
    campaign = make_campaign()
    aria = characters.create(campaign, make_character("Aria", hp=8))
    resources.set_spell_slots(campaign, "Aria", 1, 2)
    resources.use_spell_slot(campaign, "Aria", 1)
    resources.use_spell_slot(campaign, "Aria", 1)
    with pytest.raises(InvalidChangeError, match="no level 1 slot left"):
        resources.use_spell_slot(campaign, "Aria", 1)
    aria.hit_points_current = 3
    resources.long_rest(campaign, [])
    assert (aria.hit_points_current, aria.spell_slots_used) == (8, {})


def test_quest_objectives_complete_by_number_or_fragment() -> None:
    campaign = make_campaign()
    world.create_quest(
        campaign,
        Quest(
            title="Lighthouse", description="d", objectives=["Reach the cliffs", "Light the lamp"]
        ),
    )
    quest, _ = world.update_quest(campaign, "lighthouse", complete_objective="2")
    assert quest.completed_objectives == ["Light the lamp"]
    quest, _ = world.update_quest(campaign, "Lighthouse", complete_objective="cliffs")
    assert "Reach the cliffs" in quest.completed_objectives
    with pytest.raises(NotFoundError, match="1. Reach the cliffs"):
        world.update_quest(campaign, "Lighthouse", complete_objective="dragon")


def test_remove_entity_by_kind() -> None:
    campaign = make_campaign()
    world.create_npc(campaign, NPC(name="Bob"))
    assert world.remove_entity(campaign, "npc", "bob") == "Bob"
    assert campaign.npcs == {}


def test_every_duplicate_combatant_gets_a_turn() -> None:
    state = make_campaign().game_state
    fighters = [Combatant(name="Goblin", initiative=18), Combatant(name="Goblin", initiative=12)]
    combat.start(state, [*fighters, Combatant(name="Aria", initiative=5)])
    order = [combat.next_turn(state).name for _ in range(3)]
    assert order == ["Goblin 2", "Aria", "Goblin 1"]
    assert state.combat_round == 2


def test_removing_the_current_combatant_passes_the_turn() -> None:
    state = make_campaign().game_state
    combat.start(
        state, [Combatant(name=n, initiative=i) for n, i in (("A", 3), ("B", 2), ("C", 1))]
    )
    combat.next_turn(state)  # B acts
    removed, acting = combat.remove_combatant(state, "b")
    assert (removed.name, acting and acting.name) == ("B", "C")
    removed, acting = combat.remove_combatant(state, "A")
    assert acting is not None and acting.name == "C"
    assert combat.remove_combatant(state, "C")[1] is None
    assert not state.in_combat


def test_registry_revised_reports_invalid_values() -> None:
    with pytest.raises(InvalidChangeError, match="armor_class"):
        registry.revised(make_character(), {"armor_class": -1})
