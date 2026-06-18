"""game_rpg_mcp — 把 QQ 文字挂机 RPG 引擎暴露为 MCP 工具。

LLM 智能体(如 OpenClaw)通过这些工具游玩:数值/存档/挂机/排行由 game_core 权威计算,
LLM 只负责听懂人话与叙事。每个工具显式接收 world_id(世界/排行榜范围,如群id/"c2c")
和 player_id(发消息者 openid),由上层通道注入——玩家无法靠话术冒名或改数值。

存档库路径由环境变量 GAME_RPG_DB 指定,默认项目根目录 rpg.db。
"""
from __future__ import annotations

import os
import threading
import time
import random
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from game_core.config import load_config
from storage.db import get_conn, init_db
from mcp_server import handlers

_BASE = Path(__file__).resolve().parent.parent
_cfg = load_config(_BASE / "data")
_db_path = os.environ.get("GAME_RPG_DB", str(_BASE / "rpg.db"))
_conn = get_conn(_db_path)
init_db(_conn)
_lock = threading.Lock()


def _now() -> int:
    return int(time.time())


mcp = FastMCP("game_rpg_mcp")


@mcp.tool()
def rpg_register(world_id: str, player_id: str, name: str) -> dict:
    """创建一个新角色。world_id=世界/排行榜范围(如群id,单聊用 "c2c"),player_id=发消息者openid,name=角色名(1-12字)。失败返回 {ok:false,error}。"""
    with _lock:
        return handlers.h_register(_conn, _cfg, world_id, player_id, name, _now())


@mcp.tool()
def rpg_status(world_id: str, player_id: str) -> dict:
    """查询角色当前权威状态(等级/经验/血量/体力/攻防/战力/金币/层数/背包),并按真实时间结算离线体力。"""
    with _lock:
        return handlers.h_status(_conn, _cfg, world_id, player_id, _now())


@mcp.tool()
def rpg_inventory(world_id: str, player_id: str) -> dict:
    """查询角色背包与已装备物品。"""
    with _lock:
        res = handlers.h_status(_conn, _cfg, world_id, player_id, _now())
    if not res.get("ok"):
        return res
    p = res["player"]
    return {"ok": True, "name": p["name"], "equipped": p["equipped"], "inventory": p["inventory"]}


@mcp.tool()
def rpg_explore(world_id: str, player_id: str) -> dict:
    """消耗全部体力进行一次挂机探索,返回逐步冒险结果(战斗/宝箱/陷阱/叙事)与结算后的角色状态。体力不足或未注册会返回错误。"""
    with _lock:
        return handlers.h_explore(_conn, _cfg, world_id, player_id, _now(), random.Random())


@mcp.tool()
def rpg_equip(world_id: str, player_id: str, item: str) -> dict:
    """装备一件武器/护甲(item 可为物品名或id)。返回刷新后的角色状态。"""
    with _lock:
        return handlers.h_equip(_conn, _cfg, world_id, player_id, item)


@mcp.tool()
def rpg_unequip(world_id: str, player_id: str, item: str) -> dict:
    """卸下一件已装备的物品。返回刷新后的角色状态。"""
    with _lock:
        return handlers.h_unequip(_conn, _cfg, world_id, player_id, item)


@mcp.tool()
def rpg_use_item(world_id: str, player_id: str, item: str) -> dict:
    """使用一件消耗品(如治疗药水)。返回刷新后的角色状态。"""
    with _lock:
        return handlers.h_use(_conn, _cfg, world_id, player_id, item)


@mcp.tool()
def rpg_shop(world_id: str = "", player_id: str = "") -> dict:
    """查看商店在售物品与价格。(world_id/player_id 可不传。)"""
    return handlers.h_shop(_cfg)


@mcp.tool()
def rpg_buy(world_id: str, player_id: str, item: str) -> dict:
    """用金币购买商店物品(item 可为物品名或id)。返回刷新后的角色状态。金币不足会返回错误。"""
    with _lock:
        return handlers.h_buy(_conn, _cfg, world_id, player_id, item)


@mcp.tool()
def rpg_ranking(world_id: str, key: str = "level", limit: int = 10) -> dict:
    """查看本世界(world_id)排行榜。key="level" 等级榜,key="depth" 最深层榜。"""
    with _lock:
        return handlers.h_ranking(_conn, _cfg, world_id, key=key, limit=limit)
