from __future__ import annotations
import sqlite3
import math
import json
from dataclasses import dataclass, field
from game_core.models import Player, make_new_player, GameConfig
from game_core.stats import hp_max
from game_core.stamina import settle_stamina
from game_core.errors import (
    DuplicateName, CharacterNotFound, GameError, NotEnoughGold, InvalidSlot,
)
from storage import repository as repo
from storage import void_sacrifice_repo
from storage import world_boss_repo

STAMINA_REFILL_WINDOW_SECONDS = 5 * 60
STAMINA_REFILL_WINDOW_LIMIT = 300
OVERDRIVE_SECONDS = 10 * 60


@dataclass
class ItemUseSummary:
    name: str
    quantity: int


@dataclass
class BuyEquipResult:
    player: Player
    item_name: str
    cost: int


@dataclass
class HpRefillResult:
    player: Player
    hp_before: int
    hp_after: int
    hp_max: int
    used_items: list[ItemUseSummary] = field(default_factory=list)
    fully_healed: bool = False


@dataclass
class UseManyEntry:
    name: str
    requested: int
    used: int = 0
    bought: int = 0
    cost: int = 0
    error: str = ""


@dataclass
class UseManyResult:
    player: Player
    entries: list[UseManyEntry] = field(default_factory=list)
    overdrive_triggered: bool = False


@dataclass
class ReforgeResult:
    player: Player
    slot: str
    times: int
    cost: int
    old_affix: str
    new_affix: str


@dataclass
class WorldBossDamageEntry:
    user_id: str
    player_name: str
    damage: int
    damage_percent: float
    attack_count: int


@dataclass
class WorldBossRewardEntry:
    user_id: str
    player_name: str
    damage: int
    damage_percent: float
    gold: int
    items: list[tuple[str, int]] = field(default_factory=list)
    gear_item_id: str = ""


@dataclass
class WorldBossStatusResult:
    boss: sqlite3.Row | None
    bosses: list[sqlite3.Row] = field(default_factory=list)
    damage_entries: list[WorldBossDamageEntry] = field(default_factory=list)


@dataclass
class WorldBossAttackResult:
    player: Player
    boss_id: int
    boss_name: str
    damage: int
    rounds: int
    stamina_cost: int
    gold_lost: int
    player_defeated: bool
    boss_defeated: bool
    boss_hp_current: int
    boss_hp_max: int
    rewards: list[WorldBossRewardEntry] = field(default_factory=list)


@dataclass
class VoidSacrificeResult:
    player: Player
    draw_count: int
    cost: int
    draws: list["VoidSacrificeDraw"]
    pity: "VoidSacrificePity"
    ten_draw_guarantee_triggered: bool = False


def _require(conn: sqlite3.Connection, cfg: GameConfig,
             group_id: str, user_id: str) -> Player:
    p = repo.get_player(conn, group_id, user_id)
    if p is None:
        raise CharacterNotFound("你在当前世界还没有角色,先发「注册 角色名」吧~")
    return p


def _inventory_count(player: Player, item_id: str) -> int:
    return sum(inv.quantity for inv in player.inventory if inv.item_id == item_id)


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
from game_core.world_boss import (
    WORLD_BOSS_GOLD_LOSS_PCT,
    WORLD_BOSS_STAMINA_COST,
    WorldBossState,
    roll_world_boss_rewards,
    simulate_world_boss_attack,
)
from game_core.void_sacrifice import (
    VOID_SACRIFICE_SINGLE_COST,
    VOID_SACRIFICE_TEN_COST,
    VoidSacrificeDraw,
    VoidSacrificePity,
    parse_draw_count,
    roll_void_sacrifice,
)
from game_core.equipment_progression import (
    dismantle_unequipped_gear as _dismantle_unequipped_gear,
    enhance_equipped as _enhance_equipped,
    star_up_equipped as _star_up_equipped,
)


def do_explore(conn, cfg, group_id, user_id, now, rng) -> ExploreResult:
    p = _require(conn, cfg, group_id, user_id)
    res = _explore(p, cfg, now, rng)
    repo.save_player(conn, p)
    return res


def do_void_sacrifice(conn, cfg, group_id, user_id, draw_count, now, rng) -> VoidSacrificeResult:
    try:
        count = parse_draw_count(str(draw_count))
    except ValueError as exc:
        raise GameError(str(exc)) from exc
    cost = VOID_SACRIFICE_TEN_COST if count == 10 else VOID_SACRIFICE_SINGLE_COST

    player = _require(conn, cfg, group_id, user_id)
    if player.gold < cost:
        raise NotEnoughGold(f"金币不足(需 {cost},当前 {player.gold})")

    try:
        conn.execute("BEGIN IMMEDIATE")
        fresh_player = _require(conn, cfg, group_id, user_id)
        if fresh_player.gold < cost:
            raise NotEnoughGold(f"金币不足(需 {cost},当前 {fresh_player.gold})")
        fresh_player.gold -= cost
        pity = void_sacrifice_repo.get_pity(conn, group_id, user_id)
        roll = roll_void_sacrifice(count, cfg, rng, pity)

        for draw in roll.draws:
            if draw.gold_refund > 0:
                fresh_player.gold += draw.gold_refund
            if draw.consumable_id:
                _loot.add_item(fresh_player, draw.consumable_id, cfg=cfg, rng=rng)
            if draw.item_id:
                _loot.add_item(
                    fresh_player,
                    draw.item_id,
                    cfg=cfg,
                    rng=rng,
                    source=_loot.VOID_SACRIFICE_GEAR_SOURCE,
                )
        fresh_player.last_active_at = now

        repo.save_player(conn, fresh_player, commit=False)
        void_sacrifice_repo.save_pity(conn, group_id, user_id, roll.pity, now)
        conn.commit()
        return VoidSacrificeResult(
            player=fresh_player,
            draw_count=count,
            cost=cost,
            draws=roll.draws,
            pity=roll.pity,
            ten_draw_guarantee_triggered=roll.ten_draw_guarantee_triggered,
        )
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise


def do_equip(conn, cfg, group_id, user_id, item_query) -> Player:
    p = _require(conn, cfg, group_id, user_id)
    _loot.equip(p, find_item_id(cfg, item_query), cfg)
    repo.save_player(conn, p)
    return p


def do_buy_and_equip(conn, cfg, group_id, user_id, item_query) -> BuyEquipResult:
    p = _require(conn, cfg, group_id, user_id)
    item_id = find_item_id(cfg, item_query)
    item = cfg.items[item_id]
    if item.slot not in ("weapon", "armor"):
        raise InvalidSlot(f"{item.name} 不能装备")
    cost = item.price or 0
    bought = _shop.buy(p, item_id, cfg)
    for other in p.inventory:
        other_item = cfg.items.get(other.item_id)
        if other.equipped and other_item is not None and other_item.slot == item.slot:
            other.equipped = False
    bought.equipped = True
    repo.save_player(conn, p)
    return BuyEquipResult(player=p, item_name=item.name, cost=cost)


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


def _parse_gear_slot(
    slot_query: str,
    *,
    usage: str = "用法:重铸 武器/装备 [次数]",
) -> str:
    text = str(slot_query).strip()
    if text in {"武器", "weapon"}:
        return "weapon"
    if text in {"装备", "防具", "armor"}:
        return "armor"
    raise GameError(usage)


def do_reforge_equipped(conn, cfg, group_id, user_id, slot_query, times, rng) -> ReforgeResult:
    p = _require(conn, cfg, group_id, user_id)
    slot = _parse_gear_slot(slot_query)
    requested = max(1, int(times))
    affordable = p.gold // 200
    if affordable <= 0:
        raise NotEnoughGold(f"金币不足(需 200,当前 {p.gold})")
    actual = min(requested, affordable)
    old_affix = ""
    new_affix = ""
    for i in range(actual):
        previous_affix, new_affix, _ = _loot.reroll_affix(p, cfg, slot, rng)
        if i == 0:
            old_affix = previous_affix or "无词条"
    cost = actual * 200
    p.gold -= cost
    repo.save_player(conn, p)
    return ReforgeResult(
        player=p,
        slot=slot,
        times=actual,
        cost=cost,
        old_affix=old_affix,
        new_affix=new_affix,
    )


def do_refill_hp(conn, cfg, group_id, user_id) -> HpRefillResult:
    p = _require(conn, cfg, group_id, user_id)
    hp_before = p.current_hp
    maximum = hp_max(p, cfg)
    used_items: list[ItemUseSummary] = []

    healing_items = []
    for inv in p.inventory:
        item = cfg.items.get(inv.item_id)
        if item is None or item.heal <= 0 or inv.quantity <= 0:
            continue
        price = item.price if item.price is not None else 10**9
        healing_items.append((price / item.heal, item.id, item.name))
    healing_items.sort()

    for _, item_id, item_name in healing_items:
        used = 0
        while p.current_hp < maximum and _inventory_count(p, item_id) > 0:
            _loot.use_item(p, item_id, cfg)
            used += 1
        if used:
            used_items.append(ItemUseSummary(name=item_name, quantity=used))
        if p.current_hp >= maximum:
            break

    repo.save_player(conn, p)
    return HpRefillResult(
        player=p,
        hp_before=hp_before,
        hp_after=p.current_hp,
        hp_max=maximum,
        used_items=used_items,
        fully_healed=p.current_hp >= maximum,
    )


def do_use_many(conn, cfg, group_id, user_id, requests, now=None) -> UseManyResult:
    p = _require(conn, cfg, group_id, user_id)
    if now is not None:
        p.last_active_at = now
    previous_overdrive = p.overdrive_until
    entries: list[UseManyEntry] = []

    for item_query, quantity in requests:
        entry = UseManyEntry(name=str(item_query), requested=quantity)
        try:
            item_id = find_item_id(cfg, item_query)
            item = cfg.items[item_id]
            entry.name = item.name
            if item.slot != "consumable":
                raise InvalidSlot(f"{item.name} 不是消耗品")

            missing = max(0, quantity - _inventory_count(p, item_id))
            purchase_error = ""
            for _ in range(missing):
                try:
                    _shop.buy(p, item_id, cfg)
                    entry.bought += 1
                    entry.cost += item.price or 0
                except GameError as e:
                    purchase_error = str(e)
                    break

            before_stamina = p.stamina
            available = _inventory_count(p, item_id)
            if available > 0:
                entry.used = _loot.use_item(p, item_id, cfg, quantity=min(quantity, available))
                if now is not None and item.buff_type == "stamina":
                    _record_stamina_refill(p, max(0, p.stamina - before_stamina), now)
            if purchase_error:
                entry.error = purchase_error
        except GameError as e:
            entry.error = str(e)
        entries.append(entry)

    repo.save_player(conn, p)
    return UseManyResult(
        player=p,
        entries=entries,
        overdrive_triggered=p.overdrive_until > previous_overdrive,
    )


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


def do_dismantle_gear(conn, cfg, group_id, user_id, slot_filter="all"):
    p = _require(conn, cfg, group_id, user_id)
    result = _dismantle_unequipped_gear(p, cfg, slot_filter)
    if result.dismantled_count <= 0:
        raise GameError("没有可分解的未装备武器或防具")
    repo.save_player(conn, p)
    return result, p


def do_enhance_equipped(conn, cfg, group_id, user_id, slot_query, times=1, now=None):
    p = _require(conn, cfg, group_id, user_id)
    slot = _parse_gear_slot(slot_query, usage="用法:强化 武器/装备 [次数]")
    result = _enhance_equipped(p, cfg, slot, max(1, int(times)))
    if now is not None:
        p.last_active_at = now
    repo.save_player(conn, p)
    return result


def do_star_up_equipped(conn, cfg, group_id, user_id, slot_query, now=None):
    p = _require(conn, cfg, group_id, user_id)
    slot = _parse_gear_slot(slot_query, usage="用法:升星 武器/装备")
    result = _star_up_equipped(p, cfg, slot)
    if now is not None:
        p.last_active_at = now
    repo.save_player(conn, p)
    return result


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


def _world_boss_damage_entries(conn, boss) -> list[WorldBossDamageEntry]:
    if boss is None:
        return []
    hp_max = max(1, boss["hp_max"])
    entries = []
    for row in world_boss_repo.list_damage(conn, boss["id"]):
        damage = int(row["damage"])
        entries.append(WorldBossDamageEntry(
            user_id=row["user_id"],
            player_name=row["player_name"],
            damage=damage,
            damage_percent=damage / hp_max,
            attack_count=row["attack_count"],
        ))
    return entries


def _enabled_world_boss_defs(cfg):
    return sorted(
        (boss for boss in cfg.world_bosses.values() if boss.enabled),
        key=lambda boss: boss.tier,
    )


def _select_world_boss_def(cfg, boss_query=""):
    bosses = _enabled_world_boss_defs(cfg)
    if not bosses:
        raise GameError("当前没有可挑战的世界Boss")
    query = str(boss_query or "").strip()
    if not query:
        return bosses[0]
    normalized = query.lower()
    for boss in bosses:
        if query == str(boss.tier):
            return boss
        if normalized == boss.key.lower():
            return boss
        if query in {boss.name, boss.title}:
            return boss
    raise GameError(f"没有找到世界Boss: {query}")


def do_world_boss_status(conn, cfg, group_id, now, boss_query="") -> WorldBossStatusResult:
    active_count = world_boss_repo.count_active_players(conn, group_id, now)
    selected_def = _select_world_boss_def(cfg, boss_query)
    bosses = []
    selected_boss = None
    for boss_def in _enabled_world_boss_defs(cfg):
        boss = world_boss_repo.create_or_get_active_boss(
            conn, group_id, now, active_count, boss_def=boss_def
        )
        if boss is None:
            continue
        bosses.append(boss)
        if boss["boss_key"] == selected_def.key:
            selected_boss = boss
    if selected_boss is None and not boss_query and bosses:
        selected_boss = bosses[0]
    return WorldBossStatusResult(
        boss=selected_boss,
        bosses=bosses,
        damage_entries=_world_boss_damage_entries(conn, selected_boss),
    )


def _world_boss_rewards(conn, cfg, boss, now, rng, boss_def=None) -> list[WorldBossRewardEntry]:
    if world_boss_repo.reward_exists(conn, boss["id"]):
        return []

    rows = world_boss_repo.list_damage(conn, boss["id"])
    active_count = max(1, len(rows))
    rewards: list[WorldBossRewardEntry] = []
    hp_max_value = max(1, boss["hp_max"])

    for row in rows:
        player = repo.get_player(conn, boss["group_id"], row["user_id"])
        if player is None:
            continue
        damage = int(row["damage"])
        damage_percent = damage / hp_max_value
        items: list[tuple[str, int]] = []
        gear_item_id = ""
        if damage_percent < 0.01:
            gold = 200
        else:
            reward = roll_world_boss_rewards(
                damage_percent,
                player.level,
                active_count,
                cfg,
                rng,
                reward_multiplier=getattr(boss_def, "reward_multiplier", 1.0),
            )
            gold = reward.gold
            for item_id, qty in reward.consumables:
                _loot.add_item(player, item_id, qty=qty, cfg=cfg, rng=rng)
                items.append((item_id, qty))
            if reward.gear_item_id:
                _loot.add_item(player, reward.gear_item_id, cfg=cfg, rng=rng)
                gear_item_id = reward.gear_item_id

        player.gold += gold
        repo.save_player(conn, player, commit=False)
        encoded_items = list(items)
        if gear_item_id:
            encoded_items.append((gear_item_id, 1))
        world_boss_repo.record_reward(
            conn,
            boss["id"],
            boss["group_id"],
            player.user_id,
            damage,
            damage_percent,
            gold,
            json.dumps(encoded_items, ensure_ascii=False),
            now,
        )
        rewards.append(WorldBossRewardEntry(
            user_id=player.user_id,
            player_name=player.name,
            damage=damage,
            damage_percent=damage_percent,
            gold=gold,
            items=items,
            gear_item_id=gear_item_id,
        ))
    return rewards


def do_attack_world_boss(
    conn, cfg, group_id, user_id, now, rng, boss_query=""
) -> WorldBossAttackResult:
    player = _require(conn, cfg, group_id, user_id)
    settle_stamina(player, now, cfg.balance.stamina_regen_minutes, cfg.balance.stamina_max,
                   cfg.balance.stamina_regen_amount)
    if player.stamina < WORLD_BOSS_STAMINA_COST:
        raise GameError(f"体力不足(需 {WORLD_BOSS_STAMINA_COST},当前 {player.stamina})")

    boss_def = _select_world_boss_def(cfg, boss_query)
    active_count = world_boss_repo.count_active_players(conn, group_id, now)
    boss = world_boss_repo.create_or_get_active_boss(
        conn, group_id, now, active_count, boss_def=boss_def
    )
    if boss is None:
        raise GameError(f"{boss_def.name}正在休整,等待下一次刷新吧。")
    simulation = simulate_world_boss_attack(
        player,
        WorldBossState(
            hp_current=boss["hp_current"],
            atk=boss["atk"],
            defense=boss["def"],
        ),
        cfg,
        rng,
    )

    for _ in range(3):
        boss = world_boss_repo.get_active_boss(conn, group_id, boss_def.key)
        if boss is None:
            raise GameError("世界Boss已经被击败,等待下一次刷新吧。")
        effective_damage = min(simulation.damage, boss["hp_current"])
        if effective_damage <= 0:
            raise GameError("世界Boss已经被击败,等待下一次刷新吧。")

        try:
            conn.execute("BEGIN IMMEDIATE")
            fresh_player = _require(conn, cfg, group_id, user_id)
            settle_stamina(
                fresh_player,
                now,
                cfg.balance.stamina_regen_minutes,
                cfg.balance.stamina_max,
                cfg.balance.stamina_regen_amount,
            )
            if fresh_player.stamina < WORLD_BOSS_STAMINA_COST:
                raise GameError(
                    f"体力不足(需 {WORLD_BOSS_STAMINA_COST},当前 {fresh_player.stamina})"
                )
            fresh_player.stamina -= WORLD_BOSS_STAMINA_COST
            fresh_player.last_active_at = now
            gold_lost = 0
            if simulation.player_defeated:
                gold_lost = int(fresh_player.gold * WORLD_BOSS_GOLD_LOSS_PCT)
                fresh_player.gold -= gold_lost
                fresh_player.current_hp = hp_max(fresh_player, cfg)
            else:
                fresh_player.current_hp = max(1, min(hp_max(fresh_player, cfg),
                                                     simulation.player_hp_after))

            updated = world_boss_repo.apply_boss_damage(
                conn,
                boss["id"],
                boss["version"],
                effective_damage,
                now,
                cooldown_seconds=boss_def.cooldown_seconds,
            )
            if not updated:
                conn.rollback()
                continue

            world_boss_repo.add_damage(
                conn,
                boss["id"],
                group_id,
                user_id,
                fresh_player.name,
                effective_damage,
                now,
            )
            repo.save_player(conn, fresh_player, commit=False)
            updated_boss = world_boss_repo.get_boss(conn, boss["id"])
            rewards: list[WorldBossRewardEntry] = []
            boss_defeated = updated_boss["status"] == "dead"
            if boss_defeated:
                rewards = _world_boss_rewards(conn, cfg, updated_boss, now, rng, boss_def)
            conn.commit()
            return WorldBossAttackResult(
                player=fresh_player,
                boss_id=boss["id"],
                boss_name=boss["name"],
                damage=effective_damage,
                rounds=simulation.rounds,
                stamina_cost=WORLD_BOSS_STAMINA_COST,
                gold_lost=gold_lost,
                player_defeated=simulation.player_defeated,
                boss_defeated=boss_defeated,
                boss_hp_current=updated_boss["hp_current"],
                boss_hp_max=updated_boss["hp_max"],
                rewards=rewards,
            )
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise

    raise GameError("世界Boss战斗结算繁忙,请稍后再试。")


def get_due_world_boss_announcements(conn, cfg, now) -> list[WorldBossStatusResult]:
    grouped: dict[str, list[sqlite3.Row]] = {}
    for boss in world_boss_repo.list_due_announcements(conn, now):
        grouped.setdefault(boss["group_id"], []).append(boss)
    return [
        WorldBossStatusResult(
            boss=bosses[0],
            bosses=bosses,
            damage_entries=_world_boss_damage_entries(conn, bosses[0]),
        )
        for bosses in grouped.values()
    ]


def mark_world_boss_announced(conn, boss_id: int, now: int) -> None:
    world_boss_repo.mark_announced(conn, boss_id, now)
