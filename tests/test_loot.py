import random
import pytest
from pathlib import Path
from game_core.config import load_config
from game_core.models import Player, InventoryItem, MonsterDef, DropDef, Buff
from game_core.loot import (
    roll_drops, add_item, equip, unequip, use_item, sell_unequipped_gear,
)
from game_core.stats import hp_max
from game_core.errors import ItemNotFound, InvalidSlot
from game_core.errors import GameError

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CFG = load_config(DATA_DIR)


def _player():
    p = Player(group_id="g", user_id="u", name="勇者")
    p.current_hp = hp_max(p, CFG)
    return p


def test_roll_drops_respects_chance():
    m = MonsterDef(id="m", name="怪", depth_min=1, depth_max=5, hp=10, atk=1,
                   defense=1, exp=5, gold_min=1, gold_max=2,
                   drops=[DropDef(item="iron_sword", chance=1.0),
                          DropDef(item="hp_potion", chance=0.0)])
    got = roll_drops(m, random.Random(0))
    assert got == ["iron_sword"]      # chance=1 必掉,chance=0 必不掉


def test_add_item_stacks():
    p = _player()
    add_item(p, "hp_potion")
    add_item(p, "hp_potion")
    pots = [i for i in p.inventory if i.item_id == "hp_potion"]
    assert len(pots) == 1
    assert pots[0].quantity == 2


def test_equip_and_unequip():
    p = _player()
    add_item(p, "iron_sword")
    equip(p, "iron_sword", CFG)
    assert any(i.item_id == "iron_sword" and i.equipped for i in p.inventory)
    unequip(p, "iron_sword", CFG)
    assert all(not i.equipped for i in p.inventory)


def test_equip_replaces_same_slot():
    p = _player()
    add_item(p, "iron_sword")
    add_item(p, "iron_sword")
    equip(p, "iron_sword", CFG)
    equip(p, "iron_sword", CFG)        # 同为 weapon,应自动换下旧的
    equipped = [i.item_id for i in p.inventory if i.equipped]
    assert equipped == ["iron_sword"]


def test_equip_consumable_rejected():
    p = _player()
    add_item(p, "hp_potion")
    with pytest.raises(InvalidSlot):
        equip(p, "hp_potion", CFG)


def test_equip_missing_item_raises():
    p = _player()
    with pytest.raises(ItemNotFound):
        equip(p, "iron_sword", CFG)


def test_use_potion_heals_and_consumes():
    p = _player()
    p.current_hp = 10
    add_item(p, "hp_potion")
    use_item(p, "hp_potion", CFG)
    assert p.current_hp == min(hp_max(p, CFG), 10 + 40)
    assert all(i.item_id != "hp_potion" for i in p.inventory)   # 用完移除


def test_use_potion_supports_quantity():
    p = _player()
    p.current_hp = 10
    add_item(p, "hp_potion", qty=3)
    used = use_item(p, "hp_potion", CFG, quantity=3)
    assert used == 3
    assert p.current_hp == min(hp_max(p, CFG), 10 + 40 * 3)
    assert all(i.item_id != "hp_potion" for i in p.inventory)


def test_use_potion_caps_quantity_at_inventory_count():
    p = _player()
    p.current_hp = 10
    add_item(p, "hp_potion", qty=2)
    used = use_item(p, "hp_potion", CFG, quantity=5)
    assert used == 2
    assert p.current_hp == min(hp_max(p, CFG), 10 + 40 * 2)
    assert all(i.item_id != "hp_potion" for i in p.inventory)


def test_use_item_rejects_non_positive_quantity():
    p = _player()
    add_item(p, "hp_potion")
    with pytest.raises(GameError, match="数量必须大于 0"):
        use_item(p, "hp_potion", CFG, quantity=0)


def test_use_caps_at_hp_max():
    p = _player()
    p.current_hp = hp_max(p, CFG) - 5
    add_item(p, "hp_potion")
    use_item(p, "hp_potion", CFG)
    assert p.current_hp == hp_max(p, CFG)


def test_use_atk_buff_potion_adds_buff():
    p = _player()
    add_item(p, "atk_potion_minor")
    use_item(p, "atk_potion_minor", CFG)
    assert len(p.buffs) == 1
    assert p.buffs[0].type == "atk"
    assert p.buffs[0].amount == 10
    assert p.buffs[0].steps_left == 4
    assert len(p.inventory) == 0  # 用完即移出


def test_use_def_buff_overwrites_existing():
    p = _player()
    p.buffs.append(Buff(type="def", amount=3, steps_left=2))
    add_item(p, "def_potion_minor")
    use_item(p, "def_potion_minor", CFG)
    assert len(p.buffs) == 1
    assert p.buffs[0].type == "def"
    assert p.buffs[0].amount == 8       # 新值覆盖旧值
    assert p.buffs[0].steps_left == 4


def test_use_stamina_potion_restores_stamina():
    p = _player()
    p.stamina = 10
    add_item(p, "stamina_potion")
    use_item(p, "stamina_potion", CFG)
    assert p.stamina == 60              # 10 + 50


def test_use_stamina_potion_caps_at_max():
    p = _player()
    p.stamina = CFG.balance.stamina_max - 10
    add_item(p, "stamina_potion")
    use_item(p, "stamina_potion", CFG)
    assert p.stamina == CFG.balance.stamina_max


def test_sell_unequipped_gear_sells_only_weapons_and_armor_with_price():
    p = _player()
    p.gold = 10
    p.inventory = [
        InventoryItem(item_id="iron_sword", quantity=2),
        InventoryItem(item_id="fine_steel_sword", quantity=1, equipped=True),
        InventoryItem(item_id="hp_potion", quantity=3),
    ]

    result = sell_unequipped_gear(p, CFG)

    assert result.total_gold == 80
    assert p.gold == 90
    assert [(i.item_id, i.quantity, i.equipped) for i in p.inventory] == [
        ("fine_steel_sword", 1, True),
        ("hp_potion", 3, False),
    ]
    assert [(s.item_id, s.quantity, s.unit_price) for s in result.sold_items] == [
        ("iron_sword", 2, 40),
    ]


def test_sell_unequipped_gear_prices_legendary_weapon_from_lower_weapon():
    p = _player()
    p.inventory = [InventoryItem(item_id="green_dragon_blade", quantity=1)]

    result = sell_unequipped_gear(p, CFG)

    assert result.total_gold == 5040
    assert p.gold == 5040
    assert p.inventory == []
    assert result.sold_items[0].unit_price == 5040


def test_sell_unequipped_gear_prices_legendary_armor_from_lower_armor():
    p = _player()
    p.inventory = [InventoryItem(item_id="diamond_body_armor", quantity=1)]

    result = sell_unequipped_gear(p, CFG)

    assert result.total_gold == 17024
    assert p.gold == 17024
    assert p.inventory == []
    assert result.sold_items[0].unit_price == 17024


def test_sell_unequipped_void_sacrifice_gear_is_capped_below_ten_draw_cost():
    p = _player()
    p.inventory = [
        InventoryItem(item_id="diamond_body_armor", quantity=1, source="void_sacrifice")
        for _ in range(10)
    ]

    result = sell_unequipped_gear(p, CFG)

    assert result.total_gold == 8000
    assert p.gold == 8000
    assert p.inventory == []
    assert {sold.unit_price for sold in result.sold_items} == {800}
