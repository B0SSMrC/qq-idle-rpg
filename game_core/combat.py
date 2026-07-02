from __future__ import annotations
import random
from game_core.models import MonsterDef, CombatResult

MAX_ROUNDS = 50


def _hit(attacker_atk: int, defender_def: int, rng: random.Random) -> int:
    raw = max(1, attacker_atk - defender_def)
    return max(1, round(raw * rng.uniform(0.9, 1.1)))


def resolve_combat(player_atk: int, player_def: int, player_hp: int,
                   monster: MonsterDef, rng: random.Random,
                   player_lifesteal: float = 0.0,
                   player_hp_max: int | None = None) -> CombatResult:
    """自动回合制结算。返回胜负、回合数、受到的总伤害、剩余 HP。"""
    mhp = monster.hp
    start_hp = player_hp
    hp = player_hp
    max_hp = player_hp_max or player_hp
    for r in range(1, MAX_ROUNDS + 1):
        # 玩家先手
        damage = _hit(player_atk, monster.defense, rng)
        mhp -= damage
        if player_lifesteal > 0:
            hp = min(max_hp, hp + max(1, int(damage * player_lifesteal)))
        if mhp <= 0:
            return CombatResult(won=True, rounds=r,
                                damage_taken=start_hp - hp, hp_after=hp)
        # 怪反击
        hp -= _hit(monster.atk, player_def, rng)
        if hp <= 0:
            return CombatResult(won=False, rounds=r,
                                damage_taken=start_hp - hp, hp_after=hp)
    return CombatResult(won=False, rounds=MAX_ROUNDS,
                        damage_taken=start_hp - hp, hp_after=hp,
                        reason="缠斗过久撤退")
