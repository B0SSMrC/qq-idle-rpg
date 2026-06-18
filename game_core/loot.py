from __future__ import annotations
import random
from game_core.models import Player, MonsterDef, GameConfig, InventoryItem
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
    inv.quantity -= 1
    if inv.quantity <= 0:
        player.inventory.remove(inv)
