import random
import pytest
from pathlib import Path
from game_core.config import load_config
from game_core.models import Player, InventoryItem, MonsterDef, DropDef
from game_core.loot import roll_drops, add_item, equip, unequip, use_item
from game_core.stats import hp_max
from game_core.errors import ItemNotFound, InvalidSlot

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
    assert p.current_hp == min(hp_max(p, CFG), 10 + 30)
    assert all(i.item_id != "hp_potion" for i in p.inventory)   # 用完移除


def test_use_caps_at_hp_max():
    p = _player()
    p.current_hp = hp_max(p, CFG) - 5
    add_item(p, "hp_potion")
    use_item(p, "hp_potion", CFG)
    assert p.current_hp == hp_max(p, CFG)
