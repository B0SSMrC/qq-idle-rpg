from __future__ import annotations
import sqlite3
import math
from game_core.models import Player, make_new_player, GameConfig
from game_core.stats import hp_max
from game_core.stamina import settle_stamina
from game_core.errors import DuplicateName, CharacterNotFound, GameError, NotEnoughGold
from storage import repository as repo

STAMINA_REFILL_WINDOW_SECONDS = 5 * 60
STAMINA_REFILL_WINDOW_LIMIT = 300
OVERDRIVE_SECONDS = 10 * 60


def _require(conn: sqlite3.Connection, cfg: GameConfig,
             group_id: str, user_id: str) -> Player:
    p = repo.get_player(conn, group_id, user_id)
    if p is None:
        raise CharacterNotFound("你在当前世界还没有角色,先发「注册 角色名」吧~")
    return p


def register(conn: sqlite3.Connection, cfg: GameConfig,
             group_id: str, user_id: str, name: str, now: int) -> Player:
    name = name.strip()
    if not name or len(name) > 12:
        raise GameError("角色名需为 1-12 个字符")
    if repo.get_player(conn, group_id, user_id) is not None:
        raise DuplicateName("你在当前世界已经有角色啦")
    for other in repo.list_group_players(conn, group_id):
        if other.name == name:
            raise DuplicateName(f"当前世界已有人叫「{name}」,换一个吧")
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


def _record_stamina_refill(player: Player, restored: int, now: int) -> bool:
    if restored <= 0:
        return False
    if (player.stamina_refill_window_start <= 0
            or now - player.stamina_refill_window_start >= STAMINA_REFILL_WINDOW_SECONDS):
        player.stamina_refill_window_start = now
        player.stamina_refill_window_amount = 0

    player.stamina_refill_window_amount += restored
    if player.stamina_refill_window_amount > STAMINA_REFILL_WINDOW_LIMIT:
        player.overdrive_until = now + OVERDRIVE_SECONDS
        return True
    return False


def do_use(conn, cfg, group_id, user_id, item_query, quantity=1, now=None) -> Player:
    p = _require(conn, cfg, group_id, user_id)
    item_id = find_item_id(cfg, item_query)
    before_stamina = p.stamina
    _loot.use_item(p, item_id, cfg, quantity=quantity)
    if now is not None:
        p.last_active_at = now
        item = cfg.items[item_id]
        if item.buff_type == "stamina":
            _record_stamina_refill(p, max(0, p.stamina - before_stamina), now)
    repo.save_player(conn, p)
    return p


def _stamina_potion(cfg) -> ItemDef:
    for item in cfg.items.values():
        if item.buff_type == "stamina" and item.price is not None and item.buff_value > 0:
            return item
    raise GameError("商店暂时没有可用于回复体力的物品")


def do_refill_stamina(conn, cfg, group_id, user_id, now):
    p = _require(conn, cfg, group_id, user_id)
    settle_stamina(p, now, cfg.balance.stamina_regen_minutes, cfg.balance.stamina_max,
                   cfg.balance.stamina_regen_amount)
    p.last_active_at = now

    missing = max(0, cfg.balance.stamina_max - p.stamina)
    if missing == 0:
        repo.save_player(conn, p)
        return p, 0, False

    potion = _stamina_potion(cfg)
    count = math.ceil(missing / potion.buff_value)
    cost = count * potion.price
    if p.gold < cost:
        raise NotEnoughGold(f"金币不足(需 {cost},当前 {p.gold})")

    p.gold -= cost
    p.stamina = cfg.balance.stamina_max
    overdrive_triggered = _record_stamina_refill(p, missing, now)

    repo.save_player(conn, p)
    return p, cost, overdrive_triggered


def do_buy(conn, cfg, group_id, user_id, item_query) -> Player:
    p = _require(conn, cfg, group_id, user_id)
    _shop.buy(p, find_item_id(cfg, item_query), cfg)
    repo.save_player(conn, p)
    return p


def do_sell_unequipped_gear(conn, cfg, group_id, user_id):
    p = _require(conn, cfg, group_id, user_id)
    result = _loot.sell_unequipped_gear(p, cfg)
    repo.save_player(conn, p)
    return result, p


def do_travel_depth(conn, cfg, group_id, user_id, depth_query) -> Player:
    p = _require(conn, cfg, group_id, user_id)
    p.current_depth = _parse_travel_target(p, depth_query)
    repo.save_player(conn, p)
    return p


def _parse_travel_target(p: Player, depth_query) -> int:
    query = str(depth_query).strip()
    if query in {"最深", "最深层", "max", "deepest"}:
        target = p.max_depth
    else:
        try:
            target = int(query)
        except ValueError as exc:
            raise GameError("用法: 前往 层数，例如「前往 35」或「前往 最深」") from exc

    if target < 1:
        raise GameError("层数必须大于等于 1")
    if target > p.max_depth:
        raise GameError(f"你最深只到过第 {p.max_depth} 层，暂时不能前往第 {target} 层")

    return target


def do_travel_and_explore(conn, cfg, group_id, user_id, depth_query, now, rng):
    p = _require(conn, cfg, group_id, user_id)
    p.current_depth = _parse_travel_target(p, depth_query)
    res = _explore(p, cfg, now, rng)
    repo.save_player(conn, p)
    return p, res


def shop_list(cfg) -> list[ItemDef]:
    return _shop.list_shop(cfg)


def get_ranking(conn, cfg, group_id, key="level", limit=10) -> list[Player]:
    players = repo.list_group_players(conn, group_id)
    return _ranking.rank_players(players, key=key, limit=limit)
