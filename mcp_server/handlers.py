"""MCP 工具的纯逻辑层:接收显式 conn/cfg/now/rng,返回结构化 dict,便于直接测试。

不 import mcp/FastMCP。所有游戏权威逻辑都委托给 app.services(进而 game_core)。
GameError 一律转成 {"ok": False, "error": ...},让上层 LLM 拿到可读的失败原因。
"""
from __future__ import annotations

import functools
import sqlite3

from game_core.models import GameConfig, Player
from game_core.errors import GameError
from game_core.progression import exp_need
from game_core.stats import hp_max, attack, defense, power
from app import services
from storage import repository as repo


def _safe(fn):
    """统一兜底:GameError→可读错误;其它意外异常→通用错误。

    保证每个工具调用都返回 {"ok": bool, ...},绝不让堆栈/内部异常泄漏给 LLM 或玩家。
    """
    @functools.wraps(fn)
    def _wrap(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except GameError as e:
            return {"ok": False, "error": str(e)}
        except Exception:
            return {"ok": False, "error": "内部错误,请稍后再试~"}
    return _wrap


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
        "buffs": [
            {"type": b.type, "amount": b.amount, "steps_left": b.steps_left}
            for b in player.buffs
        ],
    }


@_safe
def h_register(conn: sqlite3.Connection, cfg: GameConfig,
               world_id: str, player_id: str, name: str, now: int) -> dict:
    p = services.register(conn, cfg, world_id, player_id, name, now)
    return {"ok": True, "message": f"角色「{p.name}」创建成功", "player": player_view(p, cfg)}


@_safe
def h_status(conn: sqlite3.Connection, cfg: GameConfig,
             world_id: str, player_id: str, now: int) -> dict:
    p = services.status(conn, cfg, world_id, player_id, now)
    return {"ok": True, "player": player_view(p, cfg)}


def _step_view(s, cfg: GameConfig) -> dict:
    return {
        "kind": s.kind,
        "depth": s.depth,
        "monster": s.monster,
        "won": s.won,
        "rounds": s.rounds,
        "gold": s.gold,
        "exp": s.exp,
        "items": [cfg.items[i].name if i in cfg.items else i for i in s.items],
        "hp_after": s.hp_after,
        "text": s.text,
    }


@_safe
def h_explore(conn, cfg, world_id, player_id, now, rng) -> dict:
    res = services.do_explore(conn, cfg, world_id, player_id, now, rng)
    p = repo.get_player(conn, world_id, player_id)
    out = {
        "ok": True,
        "result": {
            "steps": [_step_view(s, cfg) for s in res.steps],
            "total_gold": res.total_gold,
            "total_exp": res.total_exp,
            "items_gained": [cfg.items[i].name if i in cfg.items else i
                             for i in res.items_gained],
            "level_ups": res.level_ups,
            "defeated": res.defeated,
            "stamina_left": res.stamina_left,
            "depth_before": res.depth_before,
            "depth_after": res.depth_after,
        },
        "player": player_view(p, cfg),
    }
    if not res.steps:
        # 没有步数=体力不足(每步耗 cost_per_step),给 LLM 明确信号好叙事
        out["result"]["note"] = "体力不足,本次没有可探索的步骤,攒够体力再来下潜~"
    return out


def _player_action(fn, conn, cfg, world_id, player_id, item) -> dict:
    p = fn(conn, cfg, world_id, player_id, item)
    return {"ok": True, "player": player_view(p, cfg)}


@_safe
def h_equip(conn, cfg, world_id, player_id, item) -> dict:
    return _player_action(services.do_equip, conn, cfg, world_id, player_id, item)


@_safe
def h_unequip(conn, cfg, world_id, player_id, item) -> dict:
    return _player_action(services.do_unequip, conn, cfg, world_id, player_id, item)


@_safe
def h_use(conn, cfg, world_id, player_id, item) -> dict:
    return _player_action(services.do_use, conn, cfg, world_id, player_id, item)


@_safe
def h_buy(conn, cfg, world_id, player_id, item) -> dict:
    return _player_action(services.do_buy, conn, cfg, world_id, player_id, item)


@_safe
def h_shop(cfg: GameConfig) -> dict:
    return {
        "ok": True,
        "items": [
            {"name": it.name, "slot": it.slot, "price": it.price,
             "atk": it.atk, "def": it.defense, "hp": it.hp, "heal": it.heal}
            for it in services.shop_list(cfg)
        ],
    }


@_safe
def h_ranking(conn, cfg, world_id, key: str = "level", limit: int = 10) -> dict:
    players = services.get_ranking(conn, cfg, world_id, key=key, limit=limit)
    return {
        "ok": True,
        "key": key,
        "ranking": [
            {"rank": i + 1, "name": p.name, "level": p.level,
             "max_depth": p.max_depth, "power": power(p, cfg)}
            for i, p in enumerate(players)
        ],
    }
