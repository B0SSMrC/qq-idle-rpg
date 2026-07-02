from __future__ import annotations
from game_core.models import Player, GameConfig


def _equipped_defs(player: Player, cfg: GameConfig):
    for inv in player.inventory:
        if inv.equipped and inv.item_id in cfg.items:
            yield cfg.items[inv.item_id]


def hp_max(player: Player, cfg: GameConfig) -> int:
    b = cfg.balance
    base = b.base_hp + b.stats_hp * (player.level - 1)
    bonus = sum(d.hp for d in _equipped_defs(player, cfg))
    return base + bonus


def attack(player: Player, cfg: GameConfig) -> int:
    b = cfg.balance
    base = b.base_atk + b.stats_atk * (player.level - 1)
    bonus = sum(d.atk for d in _equipped_defs(player, cfg))
    buff_bonus = sum(buf.amount for buf in player.buffs if buf.type == "atk")
    value = base + bonus + buff_bonus
    if player.overdrive_until > player.last_active_at:
        value = int(value * 0.85)
    return value


def defense(player: Player, cfg: GameConfig) -> int:
    b = cfg.balance
    base = b.base_def + b.stats_def * (player.level - 1)
    bonus = sum(d.defense for d in _equipped_defs(player, cfg))
    buff_bonus = sum(buf.amount for buf in player.buffs if buf.type == "def")
    value = base + bonus + buff_bonus
    if player.overdrive_until > player.last_active_at:
        value = int(value * 0.8)
    return value


def power(player: Player, cfg: GameConfig) -> int:
    return int(attack(player, cfg) * 2 + defense(player, cfg) * 2
               + hp_max(player, cfg) * 0.5)
