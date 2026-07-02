import random
import pytest
from pathlib import Path
from storage.db import get_conn, init_db
from storage import repository as repo
from game_core.config import load_config
from game_core.models import InventoryItem
from game_core.errors import NotEnoughGold, ItemNotFound, CharacterNotFound, GameError, InvalidSlot
from app.services import (
    register, do_explore, do_equip, do_use, do_buy,
    do_sell_unequipped_gear, do_travel_depth, do_travel_and_explore,
    do_refill_stamina, do_buy_and_equip, do_refill_hp, do_use_many, get_ranking,
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


def test_do_buy_and_equip_buys_and_equips_shop_gear():
    conn = _conn()
    register(conn, CFG, "g", "u", "小明", now=0)
    p = repo.get_player(conn, "g", "u")
    p.gold = 100
    repo.save_player(conn, p)

    result = do_buy_and_equip(conn, CFG, "g", "u", "铁剑")

    assert result.item_name == "铁剑"
    assert result.cost == 50
    assert result.player.gold == 50
    reloaded = repo.get_player(conn, "g", "u")
    assert any(i.item_id == "iron_sword" and i.equipped for i in reloaded.inventory)


def test_do_buy_and_equip_rejects_consumables_before_spending_gold():
    conn = _conn()
    register(conn, CFG, "g", "u", "小明", now=0)
    p = repo.get_player(conn, "g", "u")
    p.gold = 100
    repo.save_player(conn, p)

    with pytest.raises(InvalidSlot, match="不能装备"):
        do_buy_and_equip(conn, CFG, "g", "u", "金疮药")

    reloaded = repo.get_player(conn, "g", "u")
    assert reloaded.gold == 100
    assert all(i.item_id != "hp_potion" for i in reloaded.inventory)


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


def test_do_use_potion_supports_quantity_and_persists():
    conn = _conn()
    register(conn, CFG, "g", "u", "小明", now=0)
    p = repo.get_player(conn, "g", "u")
    p.current_hp = 10
    p.inventory.append(InventoryItem(item_id="hp_potion", quantity=3))
    repo.save_player(conn, p)
    do_use(conn, CFG, "g", "u", "金疮药", quantity=3)
    after = repo.get_player(conn, "g", "u")
    assert after.current_hp == 120
    assert all(i.item_id != "hp_potion" for i in after.inventory)


def test_do_refill_stamina_buys_needed_stamina_potions():
    conn = _conn()
    register(conn, CFG, "g", "u", "小明", now=0)
    p = repo.get_player(conn, "g", "u")
    p.stamina = 10
    p.stamina_at = 1000
    p.gold = 200
    repo.save_player(conn, p)

    refilled, cost, overdrive_triggered = do_refill_stamina(conn, CFG, "g", "u", now=1000)

    assert refilled.stamina == CFG.balance.stamina_max
    assert cost == 160
    assert refilled.gold == 40
    assert overdrive_triggered is False


def test_do_refill_stamina_rejects_insufficient_gold():
    conn = _conn()
    register(conn, CFG, "g", "u", "小明", now=0)
    p = repo.get_player(conn, "g", "u")
    p.stamina = 0
    p.stamina_at = 1000
    p.gold = 100
    repo.save_player(conn, p)

    with pytest.raises(NotEnoughGold, match="金币不足"):
        do_refill_stamina(conn, CFG, "g", "u", now=1000)


def test_do_refill_stamina_triggers_overdrive_after_window_limit():
    conn = _conn()
    register(conn, CFG, "g", "u", "小明", now=0)
    p = repo.get_player(conn, "g", "u")
    p.stamina = 0
    p.stamina_at = 1100
    p.gold = 1000
    p.stamina_refill_window_start = 1000
    p.stamina_refill_window_amount = 250
    repo.save_player(conn, p)

    refilled, cost, overdrive_triggered = do_refill_stamina(conn, CFG, "g", "u", now=1100)

    assert cost == 160
    assert overdrive_triggered is True
    assert refilled.overdrive_until == 1100 + 10 * 60
    assert repo.get_player(conn, "g", "u").overdrive_until == 1100 + 10 * 60


def test_do_use_stamina_potion_counts_toward_overdrive_window():
    conn = _conn()
    register(conn, CFG, "g", "u", "小明", now=0)
    p = repo.get_player(conn, "g", "u")
    p.stamina = 0
    p.stamina_at = 1100
    p.stamina_refill_window_start = 1000
    p.stamina_refill_window_amount = 250
    p.inventory.append(InventoryItem(item_id="stamina_potion", quantity=2))
    repo.save_player(conn, p)

    used = do_use(conn, CFG, "g", "u", "回气丹", quantity=2, now=1100)

    assert used.stamina == CFG.balance.stamina_max
    assert used.overdrive_until == 1100 + 10 * 60


def test_do_refill_hp_uses_backpack_healing_items_until_full():
    conn = _conn()
    register(conn, CFG, "g", "u", "小明", now=0)
    p = repo.get_player(conn, "g", "u")
    p.current_hp = 10
    p.inventory = [
        InventoryItem(item_id="hp_potion", quantity=1),
        InventoryItem(item_id="greater_hp_potion", quantity=1),
    ]
    repo.save_player(conn, p)

    result = do_refill_hp(conn, CFG, "g", "u")

    assert result.hp_before == 10
    assert result.player.current_hp == 120
    assert [(item.name, item.quantity) for item in result.used_items] == [
        ("金疮药", 1),
        ("续命丹", 1),
    ]
    assert repo.get_player(conn, "g", "u").inventory == []


def test_do_refill_hp_reports_when_healing_items_run_out():
    conn = _conn()
    register(conn, CFG, "g", "u", "小明", now=0)
    p = repo.get_player(conn, "g", "u")
    p.current_hp = 10
    p.inventory = [InventoryItem(item_id="hp_potion", quantity=1)]
    repo.save_player(conn, p)

    result = do_refill_hp(conn, CFG, "g", "u")

    assert result.player.current_hp == 50
    assert result.fully_healed is False
    assert [(item.name, item.quantity) for item in result.used_items] == [("金疮药", 1)]


def test_do_use_many_auto_buys_missing_shop_consumables_and_continues():
    conn = _conn()
    register(conn, CFG, "g", "u", "小明", now=0)
    p = repo.get_player(conn, "g", "u")
    p.gold = 100
    p.inventory.append(InventoryItem(item_id="atk_potion_minor", quantity=1))
    repo.save_player(conn, p)

    result = do_use_many(
        conn, CFG, "g", "u", [("虎骨酒", 1), ("蛮牛散", 1)], now=1000
    )

    assert result.player.gold == 30
    assert [(entry.name, entry.used, entry.bought, entry.cost, entry.error)
            for entry in result.entries] == [
        ("虎骨酒", 1, 1, 70, ""),
        ("蛮牛散", 1, 0, 0, ""),
    ]
    assert result.player.buffs[0].type == "atk"
    assert result.player.buffs[0].amount == 10


def test_do_use_many_records_failures_and_keeps_processing():
    conn = _conn()
    register(conn, CFG, "g", "u", "小明", now=0)
    p = repo.get_player(conn, "g", "u")
    p.gold = 0
    p.inventory.append(InventoryItem(item_id="atk_potion_minor", quantity=1))
    repo.save_player(conn, p)

    result = do_use_many(
        conn, CFG, "g", "u", [("虎骨酒", 1), ("蛮牛散", 1)], now=1000
    )

    assert result.player.gold == 0
    assert result.entries[0].name == "虎骨酒"
    assert result.entries[0].used == 0
    assert "金币不足" in result.entries[0].error
    assert result.entries[1].name == "蛮牛散"
    assert result.entries[1].used == 1


def test_do_use_many_uses_items_bought_before_partial_purchase_failure():
    conn = _conn()
    register(conn, CFG, "g", "u", "小明", now=0)
    p = repo.get_player(conn, "g", "u")
    p.current_hp = 10
    p.gold = 25
    repo.save_player(conn, p)

    result = do_use_many(conn, CFG, "g", "u", [("金疮药", 3)], now=1000)

    assert result.player.gold == 1
    assert result.player.current_hp == 90
    assert result.entries[0].bought == 2
    assert result.entries[0].used == 2
    assert "金币不足" in result.entries[0].error


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


def test_do_travel_depth_persists_allowed_depth():
    conn = _conn()
    register(conn, CFG, "g", "u", "Player", now=0)
    p = repo.get_player(conn, "g", "u")
    p.current_depth = 60
    p.max_depth = 60
    repo.save_player(conn, p)

    moved = do_travel_depth(conn, CFG, "g", "u", "35")

    assert moved.current_depth == 35
    assert moved.max_depth == 60
    assert repo.get_player(conn, "g", "u").current_depth == 35


def test_do_travel_depth_supports_deepest_keyword():
    conn = _conn()
    register(conn, CFG, "g", "u", "Player", now=0)
    p = repo.get_player(conn, "g", "u")
    p.current_depth = 20
    p.max_depth = 73
    repo.save_player(conn, p)

    moved = do_travel_depth(conn, CFG, "g", "u", "最深")

    assert moved.current_depth == 73


def test_do_travel_depth_rejects_unreached_depth():
    conn = _conn()
    register(conn, CFG, "g", "u", "Player", now=0)
    p = repo.get_player(conn, "g", "u")
    p.max_depth = 12
    repo.save_player(conn, p)

    with pytest.raises(GameError):
        do_travel_depth(conn, CFG, "g", "u", "13")


def test_do_travel_and_explore_moves_before_exploring():
    conn = _conn()
    register(conn, CFG, "g", "u", "Player", now=0)
    p = repo.get_player(conn, "g", "u")
    p.current_depth = 60
    p.max_depth = 60
    p.stamina = 10
    repo.save_player(conn, p)

    moved, res = do_travel_and_explore(
        conn, CFG, "g", "u", "35", now=0, rng=random.Random(1)
    )

    assert res.depth_before == 35
    assert moved.current_depth == res.depth_after
    assert repo.get_player(conn, "g", "u").current_depth == res.depth_after


def test_get_ranking_group_scoped_and_sorted():
    conn = _conn()
    for u, name, lvl in [("a", "A", 3), ("b", "B", 7), ("c", "C", 5)]:
        register(conn, CFG, "g1", u, name, now=0)
        p = repo.get_player(conn, "g1", u); p.level = lvl; repo.save_player(conn, p)
    register(conn, CFG, "g2", "z", "Z", now=0)    # 别的群,不应出现
    ranked = get_ranking(conn, CFG, "g1", key="level")
    assert [p.name for p in ranked] == ["B", "C", "A"]
