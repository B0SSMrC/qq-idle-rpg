from __future__ import annotations
from game_core.models import Player


def settle_stamina(player: Player, now: int, regen_minutes: int,
                   max_stamina: int, regen_amount: int = 1) -> None:
    """按时间差现算离线体力回复;原地修改 player。

    每经过 regen_minutes 分钟回复 regen_amount 点(默认 1=旧行为)。
    """
    elapsed_min = (now - player.stamina_at) // 60
    if elapsed_min < 0:
        elapsed_min = 0
    intervals = elapsed_min // regen_minutes
    if intervals > 0:
        player.stamina = min(max_stamina, player.stamina + intervals * regen_amount)
        # 时间戳只推进"已兑现"的整段分钟,余数留到下次
        player.stamina_at += intervals * regen_minutes * 60
    if player.stamina >= max_stamina:
        player.stamina = max_stamina
        player.stamina_at = now
