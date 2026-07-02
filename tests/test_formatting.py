from pathlib import Path
from game_core.config import load_config
from game_core.models import (
    Player, InventoryItem, ExploreResult, StepLog, SellResult, SoldItem,
)
from game_core.void_sacrifice import VoidSacrificeDraw, VoidSacrificePity
from game_core.stats import hp_max
from bot.formatting import (
    render_explore, render_status, render_ranking, render_shop, render_inventory,
    render_sell_result, render_void_sacrifice, render_world_boss_status,
    render_world_boss_attack,
)
from app.services import (
    VoidSacrificeResult, WorldBossAttackResult, WorldBossDamageEntry,
    WorldBossStatusResult, WorldBossRewardEntry,
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


def test_render_status_shows_overdrive_penalty():
    p = _player()
    p.last_active_at = 1000
    p.overdrive_until = 1600
    text = render_status(p, CFG)
    assert "爆气" in text
    assert "攻击-15%" in text
    assert "防御-20%" in text


def test_render_ranking_lists_names_with_rank():
    players = [_player()]
    text = render_ranking(players, CFG, key="level")
    assert "小明" in text
    assert "🥇" in text           # 第一名奖牌
    assert "等级榜" in text


def test_render_shop_lists_priced_items():
    text = render_shop(CFG)
    assert "云游商店" in text
    assert "⚔️ 武器" in text
    assert "🛡️ 护甲" in text
    assert "💊 治疗" in text
    assert "✨ 临时增益" in text
    assert "⚡ 体力" in text
    assert "金疮药" in text
    assert "12" in text          # 金疮药价格
    assert "💊回40" in text
    assert "回气丹" in text
    assert "⚡体力+50" in text


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


def test_render_sell_result_lists_total_and_items():
    result = SellResult(sold_items=[
        SoldItem(item_id="iron_sword", name="Iron Sword", quantity=2,
                 unit_price=40, total_price=80),
    ], total_gold=80)
    text = render_sell_result(result, gold_after=392)
    assert "80" in text
    assert "392" in text
    assert "Iron Sword" in text
    assert "x2" in text


def test_render_sell_result_empty():
    text = render_sell_result(SellResult(), gold_after=312)
    assert "312" in text


def test_render_void_sacrifice_lists_rewards_and_pity():
    result = VoidSacrificeResult(
        player=Player(group_id="g", user_id="u", name="cxh", gold=9000),
        draw_count=10,
        cost=10000,
        draws=[
            VoidSacrificeDraw(rarity="common", consumable_id="def_potion_major"),
            VoidSacrificeDraw(rarity="epic", item_id="thunder_plate", guaranteed=True),
            VoidSacrificeDraw(rarity="common", gold_refund=240),
        ],
        pity=VoidSacrificePity(
            total_draws=10, draws_since_mythic_plus=10, draws_since_divine=10
        ),
        ten_draw_guarantee_triggered=True,
    )

    text = render_void_sacrifice(result, CFG)

    assert "🌌 虚空献祭 ×10" in text
    assert "消耗金币:10000" in text
    assert "金钟罩符 ×1" in text
    assert "雷纹锁子甲" in text
    assert "epic" in text
    assert "返还金币 240" in text
    assert "十连保底已生效" in text
    assert "距 mythic+ 保底:40抽" in text
    assert "距 divine 保底:110抽" in text


def test_render_void_sacrifice_uses_distinct_affixes_for_duplicate_gear():
    player = Player(group_id="g", user_id="u", name="cxh", gold=9000)
    player.inventory = [
        InventoryItem(
            item_id="thunder_plate",
            affix='{"name":"old","effects":{"hp_pct":0.14}}',
        ),
        InventoryItem(
            item_id="thunder_plate",
            affix='{"name":"new_first","effects":{"def_pct":0.09,"hp_pct":0.11}}',
        ),
        InventoryItem(
            item_id="thunder_plate",
            affix='{"name":"new_second","effects":{"atk_pct":0.12}}',
        ),
    ]
    result = VoidSacrificeResult(
        player=player,
        draw_count=2,
        cost=2000,
        draws=[
            VoidSacrificeDraw(rarity="epic", item_id="thunder_plate"),
            VoidSacrificeDraw(rarity="epic", item_id="thunder_plate"),
        ],
        pity=VoidSacrificePity(
            total_draws=2, draws_since_mythic_plus=2, draws_since_divine=2
        ),
    )

    text = render_void_sacrifice(result, CFG)

    assert "new_first(" in text
    assert "new_second(" in text
    assert "old(" not in text


def test_render_world_boss_status_lists_hp_and_damage():
    boss = {
        "name": "万劫魔君",
        "hp_current": 800,
        "hp_max": 1000,
    }
    result = WorldBossStatusResult(
        boss=boss,
        damage_entries=[
            WorldBossDamageEntry("u", "小明", 200, 0.2, 1),
        ],
    )

    text = render_world_boss_status(result, CFG)

    assert "万劫魔君" in text
    assert "800/1000" in text
    assert "小明" in text
    assert "20.0%" in text


def test_render_world_boss_attack_shows_defeat_penalty_and_rewards():
    result = WorldBossAttackResult(
        player=_player(),
        boss_id=1,
        boss_name="万劫魔君",
        damage=500,
        rounds=3,
        stamina_cost=50,
        gold_lost=20,
        player_defeated=True,
        boss_defeated=True,
        boss_hp_current=0,
        boss_hp_max=1000,
        rewards=[
            WorldBossRewardEntry(
                user_id="u",
                player_name="小明",
                damage=500,
                damage_percent=0.5,
                gold=1000,
                items=[("hp_potion", 2)],
                gear_item_id="iron_sword",
            )
        ],
    )

    text = render_world_boss_attack(result, CFG)

    assert "鏖战3回合" in text
    assert "损失金币 5%" in text
    assert "已被击败" in text
    assert "小明" in text
    assert "金疮药×2" in text
    assert "铁剑" in text
