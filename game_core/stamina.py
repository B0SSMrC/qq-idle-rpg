from __future__ import annotations
from game_core.models import Player


def settle_stamina(player: Player, now: int,
                   regen_minutes: int, max_stamina: int) -> None:
    """按时间差现算离线体力回复;原地修改 player。"""
    elapsed_min = (now - player.stamina_at) // 60
    if elapsed_min < 0:
        elapsed_min = 0
    regen = elapsed_min // regen_minutes
    if regen > 0:
        player.stamina = min(max_stamina, player.stamina + regen)
        # 时间戳只推进"已兑现"的分钟,余数留到下次
        player.stamina_at += regen * regen_minutes * 60
    if player.stamina >= max_stamina:
        player.stamina = max_stamina
        player.stamina_at = now
