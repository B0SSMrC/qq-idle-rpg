from __future__ import annotations
from game_core.models import Player


def rank_players(players: list[Player], key: str = "level",
                 limit: int = 10) -> list[Player]:
    """对(同群的)玩家列表排序取前 limit 名。

    key="level": 先比等级,再比 max_depth。
    key="depth": 比 max_depth,再比等级。
    """
    if key == "depth":
        sort_key = lambda p: (p.max_depth, p.level)
    else:
        sort_key = lambda p: (p.level, p.max_depth)
    return sorted(players, key=sort_key, reverse=True)[:limit]
