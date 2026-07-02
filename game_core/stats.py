from __future__ import annotations
from game_core.models import Player, GameConfig
from game_core.affixes import modifier_total


def _equipped_items(player: Player, cfg: GameConfig):
    for inv in player.inventory:
        if inv.equipped and inv.item_id in cfg.items:
            yield inv, cfg.items[inv.item_id]


def _equipped_affixes(player: Player, cfg: GameConfig):
    for inv in player.inventory:
        if inv.equipped and inv.item_id in cfg.items:
            yield inv.affix


def _growth_stats(inv, item):
    from game_core.equipment_progression import gear_growth_stats

    return gear_growth_stats(inv, item)


def hp_max(player: Player, cfg: GameConfig) -> int:
    b = cfg.balance
    base = b.base_hp + b.stats_hp * (player.level - 1)
    bonus = sum(_growth_stats(inv, item)[2] for inv, item in _equipped_items(player, cfg))
    value = base + bonus
    value = int(value * (1 + modifier_total(_equipped_affixes(player, cfg), "hp_pct")))
    return max(1, value)


def attack(player: Player, cfg: GameConfig) -> int:
    b = cfg.balance
    base = b.base_atk + b.stats_atk * (player.level - 1)
    bonus = sum(_growth_stats(inv, item)[0] for inv, item in _equipped_items(player, cfg))
    buff_bonus = sum(buf.amount for buf in player.buffs if buf.type == "atk")
    value = base + bonus + buff_bonus
    value = int(value * (1 + modifier_total(_equipped_affixes(player, cfg), "atk_pct")))
    if player.overdrive_until > player.last_active_at:
        value = int(value * 0.85)
    return max(1, value)


def defense(player: Player, cfg: GameConfig) -> int:
    b = cfg.balance
    base = b.base_def + b.stats_def * (player.level - 1)
    bonus = sum(_growth_stats(inv, item)[1] for inv, item in _equipped_items(player, cfg))
    buff_bonus = sum(buf.amount for buf in player.buffs if buf.type == "def")
    value = base + bonus + buff_bonus
    value = int(value * (1 + modifier_total(_equipped_affixes(player, cfg), "def_pct")))
    if player.overdrive_until > player.last_active_at:
        value = int(value * 0.8)
    return max(1, value)


def lifesteal(player: Player, cfg: GameConfig) -> float:
    return max(0.0, modifier_total(_equipped_affixes(player, cfg), "lifesteal_pct"))


def gold_bonus(player: Player, cfg: GameConfig) -> float:
    return max(0.0, modifier_total(_equipped_affixes(player, cfg), "gold_pct"))


def power(player: Player, cfg: GameConfig) -> int:
    return int(attack(player, cfg) * 2 + defense(player, cfg) * 2
               + hp_max(player, cfg) * 0.5)
