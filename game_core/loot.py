from __future__ import annotations
import random
from game_core.models import (
    Player, MonsterDef, GameConfig, InventoryItem, Buff, ItemDef,
    SoldItem, SellResult,
)
from game_core.errors import ItemNotFound, InvalidSlot
from game_core.stats import hp_max


def roll_drops(monster: MonsterDef, rng: random.Random) -> list[str]:
    return [d.item for d in monster.drops if rng.random() < d.chance]


def _find(player: Player, item_id: str) -> InventoryItem | None:
    for inv in player.inventory:
        if inv.item_id == item_id:
            return inv
    return None


def add_item(player: Player, item_id: str, qty: int = 1) -> None:
    existing = _find(player, item_id)
    if existing and not existing.equipped:
        existing.quantity += qty
    else:
        player.inventory.append(InventoryItem(item_id=item_id, quantity=qty))


def equip(player: Player, item_id: str, cfg: GameConfig) -> None:
    if item_id not in cfg.items:
        raise ItemNotFound(f"未知物品: {item_id}")
    slot = cfg.items[item_id].slot
    if slot not in ("weapon", "armor"):
        raise InvalidSlot(f"{cfg.items[item_id].name} 不能装备")
    inv = _find(player, item_id)
    if inv is None:
        raise ItemNotFound(f"背包里没有 {item_id}")
    # 卸下同槽位的其它装备
    for other in player.inventory:
        if other.equipped and cfg.items[other.item_id].slot == slot:
            other.equipped = False
    inv.equipped = True


def unequip(player: Player, item_id: str, cfg: GameConfig) -> None:
    inv = _find(player, item_id)
    if inv is None or not inv.equipped:
        raise ItemNotFound(f"{item_id} 未装备")
    inv.equipped = False


def use_item(player: Player, item_id: str, cfg: GameConfig) -> None:
    if item_id not in cfg.items:
        raise ItemNotFound(f"未知物品: {item_id}")
    item = cfg.items[item_id]
    if item.slot != "consumable":
        raise InvalidSlot(f"{item.name} 不是消耗品")
    inv = _find(player, item_id)
    if inv is None:
        raise ItemNotFound(f"背包里没有 {item.name}")
    if item.heal > 0:
        player.current_hp = min(hp_max(player, cfg), player.current_hp + item.heal)

    # 体力回复
    if item.buff_type == "stamina":
        player.stamina = min(cfg.balance.stamina_max,
                             player.stamina + item.buff_value)

    # atk/def Buff（同类型覆盖）
    if item.buff_type in ("atk", "def"):
        player.buffs = [b for b in player.buffs if b.type != item.buff_type]
        player.buffs.append(Buff(
            type=item.buff_type,
            amount=item.buff_value,
            steps_left=item.buff_steps,
        ))

    inv.quantity -= 1
    if inv.quantity <= 0:
        player.inventory.remove(inv)


def _primary_gear_stat(item: ItemDef) -> int:
    if item.slot == "weapon":
        return item.atk
    if item.slot == "armor":
        return item.defense
    return 0


def _lower_priced_gear(item: ItemDef, cfg: GameConfig) -> ItemDef | None:
    stat = _primary_gear_stat(item)
    candidates = [
        other for other in cfg.items.values()
        if other.slot == item.slot
        and other.price is not None
        and 0 < _primary_gear_stat(other) < stat
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda other: (_primary_gear_stat(other), other.price or 0))


def _gear_sale_unit_price(item: ItemDef, cfg: GameConfig) -> int | None:
    if item.price is not None:
        return max(1, int(item.price * 0.8))

    lower = _lower_priced_gear(item, cfg)
    if lower is None or lower.price is None:
        return None

    lower_stat = _primary_gear_stat(lower)
    if lower_stat <= 0:
        return None

    if item.slot == "weapon":
        raw_price = item.atk / lower_stat * lower.price * 2.7
    elif item.slot == "armor":
        raw_price = item.defense / lower_stat * 35 * lower.price
    else:
        return None
    return max(1, int(raw_price))


def sell_unequipped_gear(player: Player, cfg: GameConfig) -> SellResult:
    sold_items: list[SoldItem] = []
    kept_inventory: list[InventoryItem] = []
    total_gold = 0

    for inv in player.inventory:
        item = cfg.items.get(inv.item_id)
        if inv.equipped or item is None or item.slot not in ("weapon", "armor"):
            kept_inventory.append(inv)
            continue

        unit_price = _gear_sale_unit_price(item, cfg)
        if unit_price is None or inv.quantity <= 0:
            kept_inventory.append(inv)
            continue

        total_price = unit_price * inv.quantity
        total_gold += total_price
        sold_items.append(SoldItem(
            item_id=item.id,
            name=item.name,
            quantity=inv.quantity,
            unit_price=unit_price,
            total_price=total_price,
        ))

    player.inventory = kept_inventory
    player.gold += total_gold
    return SellResult(sold_items=sold_items, total_gold=total_gold)
