from pathlib import Path

import pytest

from game_core.config import load_config
from game_core.errors import GameError
from game_core.equipment_progression import (
    MATERIAL_ITEM_IDS,
    dismantle_unequipped_gear,
    enhance_equipped,
    gear_growth_stats,
    star_up_equipped,
)
from game_core.models import InventoryItem, Player

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CFG = load_config(DATA_DIR)


def _player():
    return Player(group_id="g", user_id="u", name="cxh", gold=100000)


def _mat_count(player, item_id):
    return sum(inv.quantity for inv in player.inventory if inv.item_id == item_id)


def test_material_items_exist_in_config():
    assert MATERIAL_ITEM_IDS <= set(CFG.items)
    assert CFG.items["refined_iron"].slot == "consumable"
    assert CFG.items["black_iron"].slot == "consumable"
    assert CFG.items["star_meteorite"].slot == "consumable"
    assert CFG.items["divine_forge_crystal"].slot == "consumable"


def test_dismantle_skips_equipped_gear_and_preserves_existing_inventory():
    p = _player()
    p.inventory = [
        InventoryItem(item_id="iron_sword", equipped=True),
        InventoryItem(item_id="iron_sword"),
        InventoryItem(item_id="fine_steel_sword"),
        InventoryItem(item_id="refined_iron", quantity=4),
        InventoryItem(item_id="hp_potion", quantity=2),
    ]

    result = dismantle_unequipped_gear(p, CFG)

    assert result.dismantled_count == 2
    assert _mat_count(p, "refined_iron") == 7
    assert any(inv.item_id == "iron_sword" and inv.equipped for inv in p.inventory)
    assert _mat_count(p, "hp_potion") == 2
    assert len([inv for inv in p.inventory if inv.item_id == "refined_iron"]) == 1


def test_enhance_equipped_consumes_gold_and_material():
    p = _player()
    p.inventory = [
        InventoryItem(item_id="iron_sword", equipped=True),
        InventoryItem(item_id="refined_iron", quantity=10),
    ]

    result = enhance_equipped(p, CFG, "weapon", times=1)

    sword = next(inv for inv in p.inventory if inv.item_id == "iron_sword")
    assert sword.enhance_level == 1
    assert result.success_count == 1
    assert result.gold_spent > 0
    assert p.gold == 100000 - result.gold_spent
    assert _mat_count(p, "refined_iron") == 9


def test_multi_enhance_stops_when_material_runs_out():
    p = _player()
    p.inventory = [
        InventoryItem(item_id="iron_sword", equipped=True),
        InventoryItem(item_id="refined_iron", quantity=2),
    ]

    result = enhance_equipped(p, CFG, "weapon", times=10)

    assert result.success_count == 2
    assert "材料不足" in result.stop_reason
    sword = next(inv for inv in p.inventory if inv.item_id == "iron_sword")
    assert sword.enhance_level == 2


def test_gear_growth_stats_apply_enhancement_and_stars():
    inv = InventoryItem(item_id="thunderclap_blade", enhance_level=10, star_level=2)
    item = CFG.items["thunderclap_blade"]

    atk, defense, hp = gear_growth_stats(inv, item)

    assert atk > item.atk
    assert defense == 0
    assert hp == 0


def test_star_up_uses_duplicate_item_first():
    p = _player()
    p.inventory = [
        InventoryItem(item_id="iron_sword", equipped=True),
        InventoryItem(item_id="iron_sword"),
    ]

    result = star_up_equipped(p, CFG, "weapon")

    equipped = next(inv for inv in p.inventory if inv.equipped)
    assert equipped.star_level == 1
    assert result.new_star_level == 1
    assert result.gold_spent == 2000
    assert len([inv for inv in p.inventory if inv.item_id == "iron_sword"]) == 1


def test_star_up_can_use_material_fallback():
    p = _player()
    p.inventory = [
        InventoryItem(item_id="iron_sword", equipped=True),
        InventoryItem(item_id="black_iron", quantity=3),
    ]

    result = star_up_equipped(p, CFG, "weapon")

    assert result.new_star_level == 1
    assert _mat_count(p, "black_iron") == 0


def test_enhance_rejects_missing_equipped_slot():
    p = _player()

    with pytest.raises(GameError):
        enhance_equipped(p, CFG, "weapon")


def test_enhance_rejects_unsupported_slots():
    p = _player()
    CFG.items["test_accessory"] = CFG.items["iron_sword"].__class__(
        id="test_accessory",
        name="Test Accessory",
        slot="accessory",
        rarity="common",
        price=1000,
    )
    p.inventory = [
        InventoryItem(item_id="test_accessory", equipped=True),
        InventoryItem(item_id="refined_iron", quantity=10),
    ]

    with pytest.raises(GameError):
        enhance_equipped(p, CFG, "accessory")


def test_star_up_rejects_unsupported_slots():
    p = _player()
    CFG.items["test_accessory"] = CFG.items["iron_sword"].__class__(
        id="test_accessory",
        name="Test Accessory",
        slot="accessory",
        rarity="common",
        price=1000,
    )
    p.inventory = [
        InventoryItem(item_id="test_accessory", equipped=True),
        InventoryItem(item_id="test_accessory"),
    ]

    with pytest.raises(GameError):
        star_up_equipped(p, CFG, "accessory")
