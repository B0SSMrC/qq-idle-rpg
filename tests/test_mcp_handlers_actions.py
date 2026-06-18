import random
from pathlib import Path
from storage.db import get_conn, init_db
from storage import repository as repo
from game_core.config import load_config
from game_core.models import InventoryItem
from mcp_server.handlers import (
    h_register, h_explore, h_equip, h_use, h_buy, h_shop, h_ranking,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CFG = load_config(DATA_DIR)


def _conn():
    conn = get_conn(":memory:")
    init_db(conn)
    return conn


def test_explore_returns_result_and_player_and_persists():
    conn = _conn()
    h_register(conn, CFG, "w", "u", "小明", now=0)
    res = h_explore(conn, CFG, "w", "u", now=60 * 60, rng=random.Random(1))
    assert res["ok"] is True
    assert isinstance(res["result"]["steps"], list)
    assert len(res["result"]["steps"]) >= 1
    # 落库:重新读档体力与返回一致
    reloaded = repo.get_player(conn, "w", "u")
    assert reloaded.stamina == res["result"]["stamina_left"] == res["player"]["stamina"]


def test_explore_missing_character_errors():
    conn = _conn()
    res = h_explore(conn, CFG, "w", "nobody", now=0, rng=random.Random(1))
    assert res["ok"] is False
    assert "error" in res


def test_buy_then_equip():
    conn = _conn()
    h_register(conn, CFG, "w", "u", "小明", now=0)
    p = repo.get_player(conn, "w", "u"); p.gold = 100; repo.save_player(conn, p)

    buy = h_buy(conn, CFG, "w", "u", "铁剑")
    assert buy["ok"] is True
    assert buy["player"]["gold"] == 50

    eq = h_equip(conn, CFG, "w", "u", "铁剑")
    assert eq["ok"] is True
    assert "铁剑" in eq["player"]["equipped"]
    assert eq["player"]["atk"] == 15   # base 10 + 剑 5


def test_buy_insufficient_gold_errors():
    conn = _conn()
    h_register(conn, CFG, "w", "u", "小明", now=0)
    res = h_buy(conn, CFG, "w", "u", "百炼钢剑")  # 价 125,金币 0
    assert res["ok"] is False
    assert "error" in res


def test_use_potion():
    conn = _conn()
    h_register(conn, CFG, "w", "u", "小明", now=0)
    p = repo.get_player(conn, "w", "u")
    p.current_hp = 10
    p.inventory.append(InventoryItem(item_id="hp_potion", quantity=1))
    repo.save_player(conn, p)
    res = h_use(conn, CFG, "w", "u", "金疮药")
    assert res["ok"] is True
    assert res["player"]["hp"] == 40           # 10 + 30


def test_shop_lists_items():
    res = h_shop(CFG)
    assert res["ok"] is True
    names = {i["name"] for i in res["items"]}
    assert "金疮药" in names
    pot = next(i for i in res["items"] if i["name"] == "金疮药")
    assert pot["price"] == 15


def test_ranking_group_scoped_and_sorted():
    conn = _conn()
    for u, name, lvl in [("a", "A", 3), ("b", "B", 7), ("c", "C", 5)]:
        h_register(conn, CFG, "w1", u, name, now=0)
        p = repo.get_player(conn, "w1", u); p.level = lvl; repo.save_player(conn, p)
    h_register(conn, CFG, "w2", "z", "Z", now=0)  # 别的世界
    res = h_ranking(conn, CFG, "w1", key="level", limit=10)
    assert res["ok"] is True
    assert [r["name"] for r in res["ranking"]] == ["B", "C", "A"]
    assert res["ranking"][0]["rank"] == 1


def test_explore_zero_stamina_returns_empty_with_note():
    conn = _conn()
    h_register(conn, CFG, "w", "u", "小明", now=0)
    res = h_explore(conn, CFG, "w", "u", now=0, rng=random.Random(1))  # 0 体力
    assert res["ok"] is True
    assert res["result"]["steps"] == []
    assert "note" in res["result"]


def test_ranking_empty_world_ok():
    conn = _conn()
    res = h_ranking(conn, CFG, "empty_world", key="level", limit=10)
    assert res["ok"] is True
    assert res["ranking"] == []


def test_equip_unknown_item_errors():
    conn = _conn()
    h_register(conn, CFG, "w", "u", "小明", now=0)
    res = h_equip(conn, CFG, "w", "u", "屠龙刀")
    assert res["ok"] is False
    assert "error" in res
