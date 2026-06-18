import random
from pathlib import Path
from game_core.config import load_config
from game_core.models import make_new_player
from game_core.stats import hp_max
from game_core.exploration import explore
from game_core.shop import buy
from game_core.loot import equip
from game_core.ranking import rank_players

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CFG = load_config(DATA_DIR)


def test_full_lifecycle():
    rng = random.Random(2026)
    now = 0
    p = make_new_player("group1", "userA", "小明",
                        now=now, start_hp=hp_max_for_new())

    # 挂机 5 小时 → 体力回满,连续探索若干轮
    for hours in range(1, 6):
        now = hours * 3600
        res = explore(p, CFG, now=now, rng=rng)
        assert res.hp_max == hp_max(p, CFG)
        assert res.depth_after >= 1

    # 攒了金币就买把剑并装备(若买得起)
    if p.gold >= CFG.items["rusty_sword"].price:
        buy(p, "rusty_sword", CFG)
        equip(p, "rusty_sword", CFG)
        # 装备后攻击力应高于基础
        from game_core.stats import attack
        assert attack(p, CFG) > CFG.balance.base_atk

    # 排行榜:把自己和两个假人一起排
    others = [
        make_new_player("group1", "userB", "小红", now=0, start_hp=100),
        make_new_player("group1", "userC", "小刚", now=0, start_hp=100),
    ]
    ranked = rank_players([p, *others], key="level", limit=10)
    assert p in ranked
    assert len(ranked) == 3


def hp_max_for_new() -> int:
    # 1 级新角色的 hp_max = base_hp
    return CFG.balance.base_hp
