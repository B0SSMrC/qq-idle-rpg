from __future__ import annotations
from game_core.models import Player, GameConfig
from game_core.stats import hp_max


def exp_need(level: int, cfg: GameConfig) -> int:
    """从 level 升到 level+1 所需经验。"""
    b = cfg.balance
    return round(b.base_exp * (b.growth ** (level - 1)))


def grant_exp(player: Player, amount: int, cfg: GameConfig) -> int:
    """给予经验,处理连续升级。返回升级次数。升级时回满血。"""
    player.exp += amount
    level_ups = 0
    while player.exp >= exp_need(player.level, cfg):
        player.exp -= exp_need(player.level, cfg)
        player.level += 1
        level_ups += 1
    if level_ups > 0:
        player.current_hp = hp_max(player, cfg)
    return level_ups


def apply_defeat(player: Player, cfg: GameConfig) -> None:
    """重伤回城:损失金币、回到第 1 层、满血。max_depth 保留。"""
    player.gold -= int(player.gold * cfg.balance.gold_loss_pct)
    player.current_depth = 1
    player.current_hp = hp_max(player, cfg)
