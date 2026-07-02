from pathlib import Path
from game_core.config import load_config
from game_core.models import Player
from game_core.progression import exp_need, grant_exp, apply_defeat
from game_core.stats import hp_max

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CFG = load_config(DATA_DIR)


def _player(level=1, exp=0, gold=0, hp=None):
    p = Player(group_id="g", user_id="u", name="勇者", level=level,
               exp=exp, gold=gold, current_depth=5, max_depth=8)
    p.current_hp = hp if hp is not None else hp_max(p, CFG)
    return p


def test_exp_need_curve():
    assert exp_need(1, CFG) == 100                  # base_exp
    assert exp_need(2, CFG) == round(100 * 1.35)    # 135
    assert exp_need(3, CFG) == round(100 * 1.35 ** 2)


def test_grant_exp_single_level():
    p = _player(level=1, exp=0)
    ups = grant_exp(p, 100, CFG)
    assert ups == 1
    assert p.level == 2
    assert p.exp == 0


def test_grant_exp_multi_level_in_one_call():
    p = _player(level=1, exp=0)
    # 100 + 135 = 235 足够升到 3 级,剩 0
    ups = grant_exp(p, 235, CFG)
    assert ups == 2
    assert p.level == 3
    assert p.exp == 0


def test_level_up_full_heals():
    p = _player(level=1, hp=10)         # 残血
    grant_exp(p, 100, CFG)
    assert p.current_hp == hp_max(p, CFG)   # 升级回满血


def test_apply_defeat_penalty():
    p = _player(level=3, gold=200, hp=1)
    apply_defeat(p, CFG)
    assert p.gold == 190                # 损失 5%
    assert p.current_depth == 5         # 战败后保留当前层
    assert p.max_depth == 8             # 历史最深保留
    assert p.current_hp == hp_max(p, CFG)   # 满血回城
