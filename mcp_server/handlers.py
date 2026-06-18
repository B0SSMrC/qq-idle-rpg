"""MCP 工具的纯逻辑层:接收显式 conn/cfg/now/rng,返回结构化 dict,便于直接测试。

不 import mcp/FastMCP。所有游戏权威逻辑都委托给 app.services(进而 game_core)。
GameError 一律转成 {"ok": False, "error": ...},让上层 LLM 拿到可读的失败原因。
"""
from __future__ import annotations

import sqlite3

from game_core.models import GameConfig, Player
from game_core.errors import GameError
from game_core.progression import exp_need
from game_core.stats import hp_max, attack, defense, power
from app import services


def player_view(player: Player, cfg: GameConfig) -> dict:
    """把 Player 序列化为对 LLM 友好的权威状态快照。"""
    return {
        "name": player.name,
        "level": player.level,
        "exp": player.exp,
        "exp_to_next": exp_need(player.level, cfg),
        "hp": player.current_hp,
        "hp_max": hp_max(player, cfg),
        "stamina": player.stamina,
        "stamina_max": cfg.balance.stamina_max,
        "atk": attack(player, cfg),
        "def": defense(player, cfg),
        "power": power(player, cfg),
        "gold": player.gold,
        "depth": player.current_depth,
        "max_depth": player.max_depth,
        "equipped": [
            cfg.items[i.item_id].name
            for i in player.inventory
            if i.equipped and i.item_id in cfg.items
        ],
        "inventory": [
            {
                "name": cfg.items[i.item_id].name if i.item_id in cfg.items else i.item_id,
                "qty": i.quantity,
                "equipped": i.equipped,
            }
            for i in player.inventory
        ],
    }


def h_register(conn: sqlite3.Connection, cfg: GameConfig,
               world_id: str, player_id: str, name: str, now: int) -> dict:
    try:
        p = services.register(conn, cfg, world_id, player_id, name, now)
        return {"ok": True, "message": f"角色「{p.name}」创建成功", "player": player_view(p, cfg)}
    except GameError as e:
        return {"ok": False, "error": str(e)}


def h_status(conn: sqlite3.Connection, cfg: GameConfig,
             world_id: str, player_id: str, now: int) -> dict:
    try:
        p = services.status(conn, cfg, world_id, player_id, now)
        return {"ok": True, "player": player_view(p, cfg)}
    except GameError as e:
        return {"ok": False, "error": str(e)}
