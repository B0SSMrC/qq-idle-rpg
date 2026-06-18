from pathlib import Path
from game_core.config import load_config
from game_core.models import Player, InventoryItem, ExploreResult, StepLog
from game_core.stats import hp_max
from bot.formatting import (
    render_explore, render_status, render_ranking, render_shop, render_inventory,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CFG = load_config(DATA_DIR)


def _player():
    p = Player(group_id="g", user_id="u", name="小明", level=4, gold=312,
               stamina=12, current_depth=6, max_depth=6)
    p.current_hp = 73
    return p


def test_render_explore_contains_key_facts():
    res = ExploreResult(
        steps=[StepLog(kind="combat", depth=4, monster="史莱姆", won=True,
                       rounds=2, gold=6, exp=15, hp_after=88),
               StepLog(kind="treasure", depth=5, gold=24, hp_after=88)],
        total_gold=30, total_exp=15, items_gained=["iron_sword"],
        level_ups=1, defeated=False, stamina_left=0,
        depth_before=3, depth_after=6, hp_after=88, hp_max=120)
    text = render_explore(_player(), res, CFG)
    assert "史莱姆" in text
    assert "30" in text          # 总金币
    assert "第6层" in text or "6" in text
    assert "升级" in text         # level_ups>0


def test_render_explore_defeat_message():
    res = ExploreResult(steps=[StepLog(kind="combat", depth=6, monster="哥布林",
                                        won=False, rounds=3, hp_after=0)],
                        total_gold=0, total_exp=0, items_gained=[], level_ups=0,
                        defeated=True, stamina_left=20, depth_before=6,
                        depth_after=1, hp_after=100, hp_max=100)
    text = render_explore(_player(), res, CFG)
    assert "回城" in text or "重伤" in text


def test_render_status_contains_stats():
    text = render_status(_player(), CFG)
    assert "小明" in text
    assert "Lv.4" in text or "4" in text
    assert "312" in text         # 金币


def test_render_ranking_lists_names_with_rank():
    players = [_player()]
    text = render_ranking(players, CFG, key="level")
    assert "小明" in text
    assert "🥇" in text           # 第一名奖牌
    assert "等级榜" in text


def test_render_shop_lists_priced_items():
    text = render_shop(CFG)
    assert "金疮药" in text
    assert "15" in text          # 金疮药价格


def test_render_inventory_lists_items_and_equipped():
    p = _player()
    p.inventory = [InventoryItem(item_id="iron_sword", quantity=1, equipped=True),
                   InventoryItem(item_id="hp_potion", quantity=3, equipped=False)]
    text = render_inventory(p, CFG)
    assert "铁剑" in text
    assert "已装备" in text
    assert "金疮药" in text
    assert "3" in text           # 数量


def test_render_inventory_empty():
    p = _player()
    p.inventory = []
    assert "空" in render_inventory(p, CFG)
