from __future__ import annotations
import sqlite3
from game_core.models import Player, make_new_player, GameConfig
from game_core.stats import hp_max
from game_core.stamina import settle_stamina
from game_core.errors import DuplicateName, CharacterNotFound, GameError
from storage import repository as repo


def _require(conn: sqlite3.Connection, cfg: GameConfig,
             group_id: str, user_id: str) -> Player:
    p = repo.get_player(conn, group_id, user_id)
    if p is None:
        raise CharacterNotFound("你在本群还没有角色,先发「注册 角色名」吧~")
    return p


def register(conn: sqlite3.Connection, cfg: GameConfig,
             group_id: str, user_id: str, name: str, now: int) -> Player:
    name = name.strip()
    if not name or len(name) > 12:
        raise GameError("角色名需为 1-12 个字符")
    if repo.get_player(conn, group_id, user_id) is not None:
        raise DuplicateName("你在本群已经有角色啦")
    for other in repo.list_group_players(conn, group_id):
        if other.name == name:
            raise DuplicateName(f"本群已有人叫「{name}」,换一个吧")
    # 用 1 级 hp_max 初始化满血
    probe = Player(group_id=group_id, user_id=user_id, name=name)
    start_hp = hp_max(probe, cfg)
    player = make_new_player(group_id, user_id, name, now=now, start_hp=start_hp)
    return repo.create_player(conn, player)


def status(conn: sqlite3.Connection, cfg: GameConfig,
           group_id: str, user_id: str, now: int) -> Player:
    p = _require(conn, cfg, group_id, user_id)
    settle_stamina(p, now, cfg.balance.stamina_regen_minutes, cfg.balance.stamina_max,
                   cfg.balance.stamina_regen_amount)
    p.last_active_at = now
    repo.save_player(conn, p)
    return p


from game_core.config import find_item_id
from game_core.exploration import explore as _explore
from game_core import loot as _loot, shop as _shop, ranking as _ranking
from game_core.models import ExploreResult, ItemDef


def do_explore(conn, cfg, group_id, user_id, now, rng) -> ExploreResult:
    p = _require(conn, cfg, group_id, user_id)
    res = _explore(p, cfg, now, rng)
    repo.save_player(conn, p)
    return res


def do_equip(conn, cfg, group_id, user_id, item_query) -> Player:
    p = _require(conn, cfg, group_id, user_id)
    _loot.equip(p, find_item_id(cfg, item_query), cfg)
    repo.save_player(conn, p)
    return p


def do_unequip(conn, cfg, group_id, user_id, item_query) -> Player:
    p = _require(conn, cfg, group_id, user_id)
    _loot.unequip(p, find_item_id(cfg, item_query), cfg)
    repo.save_player(conn, p)
    return p


def do_use(conn, cfg, group_id, user_id, item_query) -> Player:
    p = _require(conn, cfg, group_id, user_id)
    _loot.use_item(p, find_item_id(cfg, item_query), cfg)
    repo.save_player(conn, p)
    return p


def do_buy(conn, cfg, group_id, user_id, item_query) -> Player:
    p = _require(conn, cfg, group_id, user_id)
    _shop.buy(p, find_item_id(cfg, item_query), cfg)
    repo.save_player(conn, p)
    return p


def shop_list(cfg) -> list[ItemDef]:
    return _shop.list_shop(cfg)


def get_ranking(conn, cfg, group_id, key="level", limit=10) -> list[Player]:
    players = repo.list_group_players(conn, group_id)
    return _ranking.rank_players(players, key=key, limit=limit)
