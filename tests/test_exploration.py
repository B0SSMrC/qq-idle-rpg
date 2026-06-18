import random
from pathlib import Path
from game_core.config import load_config
from game_core.models import Player
from game_core.stats import hp_max
from game_core.exploration import explore

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CFG = load_config(DATA_DIR)


def _player(stamina, now=10_000, level=1):
    p = Player(group_id="g", user_id="u", name="勇者",
               level=level, stamina=stamina, stamina_at=now)
    p.current_hp = hp_max(p, CFG)
    return p


def test_no_stamina_means_no_steps():
    p = _player(stamina=0)
    res = explore(p, CFG, now=p.stamina_at, rng=random.Random(0))
    assert res.steps == []
    assert res.stamina_left == 0


def test_explore_consumes_stamina_in_steps():
    # 体力 10,每步耗 5 → 恰好 2 步(无中途战败时)
    p = _player(stamina=10)
    res = explore(p, CFG, now=p.stamina_at, rng=random.Random(2))
    assert res.stamina_left < 10
    assert p.stamina == res.stamina_left
    # 步数 = 消耗的体力 / 5,且 ≤ 2
    assert 1 <= len(res.steps) <= 2


def test_offline_stamina_settled_before_exploring():
    # 初始 0 体力,但已过去 60 分钟(每5分钟+1 → +12)
    p = _player(stamina=0, now=10_000)
    later = 10_000 + 60 * 60
    res = explore(p, CFG, now=later, rng=random.Random(3))
    # 先结算出 12 体力,够走 2 步(每步5),最终应有探索发生
    assert len(res.steps) >= 1


def test_max_depth_tracks_progress():
    p = _player(stamina=50, level=50)   # 高级保证不会战败
    start_max = p.max_depth
    res = explore(p, CFG, now=p.stamina_at, rng=random.Random(5))
    assert res.depth_after >= res.depth_before
    assert p.max_depth >= start_max
    assert p.max_depth == max(start_max, res.depth_after)


def test_defeat_resets_depth_to_one():
    # 1 级、深处、塞满体力,对上强怪极可能战败;遍历多个种子找到一次战败
    defeated_seen = False
    for seed in range(50):
        p = Player(group_id="g", user_id="u", name="勇者",
                   level=1, stamina=50, stamina_at=0,
                   current_depth=15, max_depth=15)
        p.current_hp = hp_max(p, CFG)
        res = explore(p, CFG, now=0, rng=random.Random(seed))
        if res.defeated:
            defeated_seen = True
            assert p.current_depth == 1        # 回城
            assert p.max_depth >= 15           # 历史最深保留
            assert p.current_hp == hp_max(p, CFG)
            break
    assert defeated_seen, "50 个种子内应至少出现一次战败"


def test_result_totals_are_consistent():
    p = _player(stamina=50, level=80)   # 高级,稳赢,稳定积累
    res = explore(p, CFG, now=p.stamina_at, rng=random.Random(11))
    assert res.total_exp == sum(s.exp for s in res.steps)
    assert res.total_gold == sum(s.gold for s in res.steps)
    assert res.hp_max == hp_max(p, CFG)


def test_explore_does_not_crash_when_no_event_matches_depth():
    # 把所有事件限制在 1-2 层,再到第 99 层探索:depth 过滤后事件池为空,
    # 应回退到全部事件而非抛 IndexError。
    import copy
    cfg = copy.deepcopy(CFG)
    for e in cfg.events:
        e.depth_max = 2
    p = _player(stamina=10)
    p.current_depth = 99
    res = explore(p, cfg, now=p.stamina_at, rng=random.Random(1))
    assert len(res.steps) >= 1          # 没有崩溃,正常产出步骤
