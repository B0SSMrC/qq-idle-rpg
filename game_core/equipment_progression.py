from __future__ import annotations

from dataclasses import dataclass, field
from math import floor

from game_core.errors import GameError, NotEnoughGold
from game_core.loot import add_item
from game_core.models import GameConfig, InventoryItem, ItemDef, Player

MATERIAL_ITEM_IDS = {
    "refined_iron",
    "black_iron",
    "star_meteorite",
    "divine_forge_crystal",
}

ENHANCE_CAPS = {
    "common": 5,
    "uncommon": 8,
    "rare": 12,
    "epic": 16,
    "legendary": 20,
    "mythic": 25,
    "divine": 30,
}

RARITY_MULTIPLIERS = {
    "common": 0.25,
    "uncommon": 0.35,
    "rare": 0.50,
    "epic": 0.75,
    "legendary": 1.00,
    "mythic": 1.35,
    "divine": 1.80,
}

RARITY_PRICE_FLOOR = {
    "legendary": 3000,
    "mythic": 6000,
    "divine": 12000,
}

STAR_BONUS = {
    0: 0.00,
    1: 0.08,
    2: 0.16,
    3: 0.25,
    4: 0.35,
    5: 0.50,
}


@dataclass
class MaterialCost:
    item_id: str
    quantity: int


@dataclass
class DismantledGear:
    item_id: str
    name: str
    quantity: int
    materials: list[MaterialCost] = field(default_factory=list)


@dataclass
class DismantleResult:
    dismantled: list[DismantledGear] = field(default_factory=list)
    materials: dict[str, int] = field(default_factory=dict)

    @property
    def dismantled_count(self) -> int:
        return sum(entry.quantity for entry in self.dismantled)


@dataclass
class EnhanceResult:
    item_name: str
    slot: str
    old_level: int
    new_level: int
    requested: int
    success_count: int
    gold_spent: int
    materials_spent: dict[str, int] = field(default_factory=dict)
    stop_reason: str = ""


@dataclass
class StarUpResult:
    item_name: str
    slot: str
    old_star_level: int
    new_star_level: int
    gold_spent: int
    duplicate_spent: int = 0
    materials_spent: dict[str, int] = field(default_factory=dict)


def _equipped(player: Player, cfg: GameConfig, slot: str) -> tuple[InventoryItem, ItemDef]:
    for inv in player.inventory:
        item = cfg.items.get(inv.item_id)
        if inv.equipped and item is not None and item.slot == slot:
            return inv, item
    label = "武器" if slot == "weapon" else "装备"
    raise GameError(f"当前没有装备的{label}")


def _material_count(player: Player, item_id: str) -> int:
    return sum(inv.quantity for inv in player.inventory if inv.item_id == item_id)


def _consume_material(player: Player, item_id: str, quantity: int) -> None:
    if _material_count(player, item_id) < quantity:
        raise GameError(f"材料不足：需要 {item_id} x{quantity}")

    remaining = quantity
    for inv in list(player.inventory):
        if inv.item_id != item_id:
            continue
        used = min(inv.quantity, remaining)
        inv.quantity -= used
        remaining -= used
        if inv.quantity <= 0:
            player.inventory.remove(inv)
        if remaining <= 0:
            return


def _grant_material(player: Player, item_id: str, quantity: int, cfg: GameConfig) -> None:
    add_item(player, item_id, qty=quantity, cfg=cfg)


def _dismantle_material_for_rarity(rarity: str) -> MaterialCost:
    mapping = {
        "common": MaterialCost("refined_iron", 1),
        "uncommon": MaterialCost("refined_iron", 2),
        "rare": MaterialCost("black_iron", 1),
        "epic": MaterialCost("black_iron", 2),
        "legendary": MaterialCost("star_meteorite", 1),
        "mythic": MaterialCost("star_meteorite", 2),
        "divine": MaterialCost("divine_forge_crystal", 1),
    }
    return mapping.get(rarity, MaterialCost("refined_iron", 1))


def dismantle_unequipped_gear(
    player: Player, cfg: GameConfig, slot_filter: str = "all"
) -> DismantleResult:
    kept: list[InventoryItem] = []
    granted: dict[str, int] = {}
    result = DismantleResult()

    for inv in player.inventory:
        item = cfg.items.get(inv.item_id)
        if inv.equipped or item is None or item.slot not in ("weapon", "armor"):
            kept.append(inv)
            continue
        if slot_filter != "all" and item.slot != slot_filter:
            kept.append(inv)
            continue

        material = _dismantle_material_for_rarity(item.rarity)
        total_qty = material.quantity * inv.quantity
        granted[material.item_id] = granted.get(material.item_id, 0) + total_qty
        result.materials[material.item_id] = result.materials.get(material.item_id, 0) + total_qty
        result.dismantled.append(
            DismantledGear(
                item_id=item.id,
                name=item.name,
                quantity=inv.quantity,
                materials=[MaterialCost(material.item_id, total_qty)],
            )
        )

    player.inventory = kept
    for item_id, quantity in granted.items():
        _grant_material(player, item_id, quantity, cfg)
    return result


def _growth_stat(base: int, enhance_level: int, star_level: int) -> int:
    if base == 0:
        return 0
    sign = 1 if base > 0 else -1
    enhanced_delta = sign * max(1, floor(abs(base) * 0.04 * enhance_level)) if enhance_level else 0
    enhanced = base + enhanced_delta
    return int(enhanced * (1 + STAR_BONUS.get(star_level, 0.0)))


def gear_growth_stats(inv: InventoryItem, item: ItemDef) -> tuple[int, int, int]:
    return (
        _growth_stat(item.atk, inv.enhance_level, inv.star_level),
        _growth_stat(item.defense, inv.enhance_level, inv.star_level),
        _growth_stat(item.hp, inv.enhance_level, inv.star_level),
    )


def _enhance_cap(item: ItemDef) -> int:
    return ENHANCE_CAPS.get(item.rarity, 5)


def _base_price(item: ItemDef) -> int:
    if item.price is not None:
        return item.price
    return RARITY_PRICE_FLOOR.get(item.rarity, 1000)


def _enhance_gold_cost(item: ItemDef, target_level: int) -> int:
    multiplier = RARITY_MULTIPLIERS.get(item.rarity, 0.5)
    return max(1, floor(_base_price(item) * multiplier * (1 + target_level * 0.18)))


def _enhance_material(item: ItemDef, target_level: int) -> MaterialCost:
    if item.rarity == "divine" and target_level <= 8:
        return MaterialCost("star_meteorite", 1)
    if item.rarity == "mythic" and target_level <= 8:
        return MaterialCost("black_iron", 1)
    if target_level <= 8:
        return MaterialCost("refined_iron", 1)
    if target_level <= 16:
        return MaterialCost("black_iron", 1)
    if target_level <= 24:
        return MaterialCost("star_meteorite", 1)
    return MaterialCost("divine_forge_crystal", 1)


def enhance_equipped(
    player: Player, cfg: GameConfig, slot: str, times: int = 1
) -> EnhanceResult:
    inv, item = _equipped(player, cfg, slot)
    requested = max(1, int(times))
    old_level = inv.enhance_level
    gold_spent = 0
    materials_spent: dict[str, int] = {}
    stop_reason = ""

    for _ in range(requested):
        if inv.enhance_level >= _enhance_cap(item):
            stop_reason = "这件装备已达到强化上限。"
            break

        target = inv.enhance_level + 1
        gold_cost = _enhance_gold_cost(item, target)
        material = _enhance_material(item, target)

        if player.gold < gold_cost:
            stop_reason = f"金币不足(需 {gold_cost}, 当前 {player.gold})"
            break
        if _material_count(player, material.item_id) < material.quantity:
            stop_reason = f"材料不足：需要 {cfg.items[material.item_id].name} x{material.quantity}。"
            break

        player.gold -= gold_cost
        _consume_material(player, material.item_id, material.quantity)
        inv.enhance_level = target
        gold_spent += gold_cost
        materials_spent[material.item_id] = materials_spent.get(material.item_id, 0) + material.quantity

    success_count = inv.enhance_level - old_level
    if success_count == 0 and stop_reason:
        if stop_reason.startswith("金币不足"):
            raise NotEnoughGold(stop_reason)
        raise GameError(stop_reason)

    return EnhanceResult(
        item_name=item.name,
        slot=slot,
        old_level=old_level,
        new_level=inv.enhance_level,
        requested=requested,
        success_count=success_count,
        gold_spent=gold_spent,
        materials_spent=materials_spent,
        stop_reason=stop_reason,
    )


def _star_cost(target_star: int) -> tuple[int, list[MaterialCost]]:
    fallback = {
        1: (2000, [MaterialCost("black_iron", 3)]),
        2: (5000, [MaterialCost("black_iron", 6)]),
        3: (10000, [MaterialCost("star_meteorite", 4)]),
        4: (20000, [MaterialCost("divine_forge_crystal", 1), MaterialCost("star_meteorite", 5)]),
        5: (40000, [MaterialCost("divine_forge_crystal", 3)]),
    }
    return fallback[target_star]


def _consume_duplicate(player: Player, item_id: str, count: int) -> bool:
    duplicates = [
        inv for inv in player.inventory
        if not inv.equipped and inv.item_id == item_id
    ]
    if len(duplicates) < count:
        return False
    for inv in duplicates[:count]:
        player.inventory.remove(inv)
    return True


def star_up_equipped(player: Player, cfg: GameConfig, slot: str) -> StarUpResult:
    inv, item = _equipped(player, cfg, slot)
    if inv.star_level >= 5:
        raise GameError("这件装备已满星。")

    old_star = inv.star_level
    target_star = old_star + 1
    gold_cost, fallback_materials = _star_cost(target_star)
    if player.gold < gold_cost:
        raise NotEnoughGold(f"金币不足(需 {gold_cost}, 当前 {player.gold})")

    duplicate_needed = 2 if target_star == 5 else 1
    duplicate_spent = 0
    materials_spent: dict[str, int] = {}

    if _consume_duplicate(player, item.id, duplicate_needed):
        duplicate_spent = duplicate_needed
    else:
        for cost in fallback_materials:
            if _material_count(player, cost.item_id) < cost.quantity:
                name = cfg.items[cost.item_id].name
                raise GameError(
                    f"升星材料不足：需要同名装备 x{duplicate_needed}，或 {name} x{cost.quantity}。"
                )
        for cost in fallback_materials:
            _consume_material(player, cost.item_id, cost.quantity)
            materials_spent[cost.item_id] = materials_spent.get(cost.item_id, 0) + cost.quantity

    player.gold -= gold_cost
    inv.star_level = target_star
    return StarUpResult(
        item_name=item.name,
        slot=slot,
        old_star_level=old_star,
        new_star_level=target_star,
        gold_spent=gold_cost,
        duplicate_spent=duplicate_spent,
        materials_spent=materials_spent,
    )
