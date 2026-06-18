import random
from game_core.models import MonsterDef, CombatResult
from game_core.combat import resolve_combat


def _monster(hp=30, atk=5, defense=1):
    return MonsterDef(id="m", name="怪", depth_min=1, depth_max=5,
                      hp=hp, atk=atk, defense=defense, exp=10,
                      gold_min=1, gold_max=3, drops=[])


def test_strong_player_always_wins():
    rng = random.Random(42)
    m = _monster(hp=10, atk=1, defense=0)
    r = resolve_combat(player_atk=50, player_def=50, player_hp=100,
                       monster=m, rng=rng)
    assert r.won is True
    assert r.hp_after == 100          # 怪打不动玩家(伤害最低 1,但秒杀前未被摸到)
    assert r.rounds >= 1


def test_weak_player_loses():
    rng = random.Random(1)
    m = _monster(hp=1000, atk=80, defense=50)
    r = resolve_combat(player_atk=10, player_def=1, player_hp=30,
                       monster=m, rng=rng)
    assert r.won is False
    assert r.hp_after <= 0


def test_minimum_damage_is_one():
    rng = random.Random(7)
    # 玩家攻击 5 远低于怪防御 100 → 仍应每回合至少造成 1 点,不会死循环
    m = _monster(hp=3, atk=1, defense=100)
    r = resolve_combat(player_atk=5, player_def=100, player_hp=100,
                       monster=m, rng=rng)
    assert r.won is True
    assert r.rounds <= 3              # 3 血、每次至少 1 → ≤3 回合


def test_deterministic_with_same_seed():
    m = _monster(hp=40, atk=10, defense=2)
    r1 = resolve_combat(20, 5, 50, m, random.Random(123))
    r2 = resolve_combat(20, 5, 50, m, random.Random(123))
    assert (r1.won, r1.rounds, r1.hp_after) == (r2.won, r2.rounds, r2.hp_after)
