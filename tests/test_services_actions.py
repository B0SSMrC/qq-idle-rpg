import random
import pytest
from pathlib import Path
from storage.db import get_conn, init_db
from storage import repository as repo
from game_core.config import load_config
from game_core.models import InventoryItem
from game_core.errors import NotEnoughGold, ItemNotFound, CharacterNotFound
from app.services import (
    register, do_explore, do_equip, do_use, do_buy,
    do_sell_unequipped_gear, get_ranking,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CFG = load_config(DATA_DIR)


def _conn():
    conn = get_conn(":memory:")
    init_db(conn)
    return conn


def test_do_explore_persists_progress():
    conn = _conn()
    register(conn, CFG, "g", "u", "小明", now=0)
    res = do_explore(conn, CFG, "g", "u", now=60 * 60, rng=random.Random(1))
    assert len(res.steps) >= 1
    # 重新读档:体力应已被消耗并落库
    reloaded = repo.get_player(conn, "g", "u")
    assert reloaded.stamina == res.stamina_left


def test_do_explore_requires_character():
    conn = _conn()
    with pytest.raises(CharacterNotFound):
        do_explore(conn, CFG, "g", "nobody", now=0, rng=random.Random(1))


def test_do_buy_and_equip_persist():
    conn = _conn()
    register(conn, CFG, "g", "u", "小明", now=0)
    p = repo.get_player(conn, "g", "u")
    p.gold = 100
    repo.save_player(conn, p)

    do_buy(conn, CFG, "g", "u", "铁剑")     # 中文名购买,价 50
    after_buy = repo.get_player(conn, "g", "u")
    assert after_buy.gold == 50
    assert any(i.item_id == "iron_sword" for i in after_buy.inventory)

    do_equip(conn, CFG, "g", "u", "铁剑")
    after_equip = repo.get_player(conn, "g", "u")
    assert any(i.item_id == "iron_sword" and i.equipped for i in after_equip.inventory)


def test_do_buy_insufficient_gold():
    conn = _conn()
    register(conn, CFG, "g", "u", "小明", now=0)   # 0 金币
    with pytest.raises(NotEnoughGold):
        do_buy(conn, CFG, "g", "u", "百炼钢剑")    # 价 125


def test_do_use_potion():
    conn = _conn()
    register(conn, CFG, "g", "u", "小明", now=0)
    p = repo.get_player(conn, "g", "u")
    p.current_hp = 10
    p.inventory.append(InventoryItem(item_id="hp_potion", quantity=1))
    repo.save_player(conn, p)
    do_use(conn, CFG, "g", "u", "金疮药")
    after = repo.get_player(conn, "g", "u")
    assert after.current_hp == 50                 # 10 + 40
    assert all(i.item_id != "hp_potion" for i in after.inventory)


def test_do_sell_unequipped_gear_persists_gold_and_inventory():
    conn = _conn()
    register(conn, CFG, "g", "u", "灏忔槑", now=0)
    p = repo.get_player(conn, "g", "u")
    p.inventory = [
        InventoryItem(item_id="iron_sword", quantity=2),
        InventoryItem(item_id="fine_steel_sword", quantity=1, equipped=True),
        InventoryItem(item_id="hp_potion", quantity=3),
    ]
    repo.save_player(conn, p)

    result, sold_player = do_sell_unequipped_gear(conn, CFG, "g", "u")

    assert result.total_gold == 80
    assert sold_player.gold == 80
    reloaded = repo.get_player(conn, "g", "u")
    assert reloaded.gold == 80
    assert [(i.item_id, i.quantity, i.equipped) for i in reloaded.inventory] == [
        ("fine_steel_sword", 1, True),
        ("hp_potion", 3, False),
    ]


def test_get_ranking_group_scoped_and_sorted():
    conn = _conn()
    for u, name, lvl in [("a", "A", 3), ("b", "B", 7), ("c", "C", 5)]:
        register(conn, CFG, "g1", u, name, now=0)
        p = repo.get_player(conn, "g1", u); p.level = lvl; repo.save_player(conn, p)
    register(conn, CFG, "g2", "z", "Z", now=0)    # 别的群,不应出现
    ranked = get_ranking(conn, CFG, "g1", key="level")
    assert [p.name for p in ranked] == ["B", "C", "A"]
