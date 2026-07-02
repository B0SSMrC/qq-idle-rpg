# Equipment Progression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add equipment dismantling, enhancement, and star-up so players can convert extra gear into materials and steadily improve equipped weapons and armor.

**Architecture:** Keep the progression math in a new focused `game_core.equipment_progression` module. Persist enhancement/star fields on `InventoryItem`, reuse existing repository save/load patterns, expose transactional service functions from `app.services`, and connect them to OneBot commands plus formatting/image display.

**Tech Stack:** Python 3.10+, SQLite, PyYAML config, NoneBot OneBot v11, Pillow inventory images, pytest.

## Global Constraints

- Existing gear without new fields must load as `enhance_level = 0` and `star_level = 0`.
- Only weapons and armor can be enhanced, starred, or dismantled.
- Batch dismantle must never remove equipped gear.
- Enhancement applies to equipped gear and supports an optional count.
- Star-up applies to equipped gear and is one attempt per command in the first version.
- Affixes stay independent and continue applying at the player-stat layer.
- One-click selling remains unchanged.
- Do not reintroduce QQ official bot or MCP framework code.
- Use test-first implementation for every task.

---

## File Structure

- Modify `game_core/models.py`: add `enhance_level` and `star_level` to `InventoryItem`.
- Modify `storage/db.py`: add `inventory.enhance_level` and `inventory.star_level` to schema and migrations.
- Modify `storage/repository.py`: load/save new inventory fields.
- Modify `data/items.yaml`: add four material items.
- Create `game_core/equipment_progression.py`: caps, costs, material rewards, stat growth helpers, dismantle/enhance/star-up core functions.
- Modify `game_core/stats.py`: calculate equipped gear stats through enhancement and star growth.
- Modify `bot/formatting.py`: show enhancement/star labels and material stats in status, inventory, and result renderers.
- Modify `bot/inventory_image.py`: show enhancement/star labels and grown gear stats in image rows.
- Modify `app/services.py`: add service result dataclasses and transactional service functions.
- Modify `bot/fuzzy_commands.py`: route explicit dismantle/enhance/star-up variants.
- Modify `bot/plugins/rpg.py`: add OneBot commands and fuzzy dispatch branches.
- Modify `docs/game-commands.md`: document new commands and expected outputs.
- Add/modify tests in `tests/test_db.py`, `tests/test_repository.py`, `tests/test_equipment_progression.py`, `tests/test_stats.py`, `tests/test_services_actions.py`, `tests/test_formatting.py`, `tests/test_inventory_image.py`, and `tests/test_fuzzy_commands.py`.

---

### Task 1: Persist Equipment Growth Fields

**Files:**
- Modify: `game_core/models.py`
- Modify: `storage/db.py`
- Modify: `storage/repository.py`
- Test: `tests/test_db.py`
- Test: `tests/test_repository.py`

**Interfaces:**
- Produces: `InventoryItem.enhance_level: int`
- Produces: `InventoryItem.star_level: int`
- Produces DB columns `inventory.enhance_level` and `inventory.star_level`

- [ ] **Step 1: Write failing DB migration test**

Add this test to `tests/test_db.py`:

```python
def test_init_db_adds_inventory_growth_columns_to_existing_inventory_table():
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            stamina_at INTEGER NOT NULL,
            current_hp INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            last_active_at INTEGER NOT NULL,
            UNIQUE(group_id, user_id)
        );
        CREATE TABLE inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL REFERENCES players(id),
            item_id TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            equipped INTEGER NOT NULL DEFAULT 0,
            affix TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT ''
        );
    """)

    init_db(conn)

    cols = {r["name"] for r in conn.execute("PRAGMA table_info(inventory)")}
    assert "enhance_level" in cols
    assert "star_level" in cols
```

- [ ] **Step 2: Write failing repository round-trip test**

Add this test to `tests/test_repository.py`:

```python
def test_save_and_load_inventory_growth_fields():
    conn = _conn()
    p = create_player(conn, _player())
    p.inventory.append(InventoryItem(
        item_id="iron_sword",
        quantity=1,
        equipped=True,
        enhance_level=7,
        star_level=2,
    ))
    save_player(conn, p)

    loaded = get_player(conn, "g", "u")
    assert loaded.inventory[0].enhance_level == 7
    assert loaded.inventory[0].star_level == 2
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
pytest tests/test_db.py::test_init_db_adds_inventory_growth_columns_to_existing_inventory_table tests/test_repository.py::test_save_and_load_inventory_growth_fields -q
```

Expected: fail because `InventoryItem` has no `enhance_level`/`star_level` fields or DB columns.

- [ ] **Step 4: Add model fields**

In `game_core/models.py`, change `InventoryItem` to:

```python
@dataclass
class InventoryItem:
    item_id: str
    quantity: int = 1
    equipped: bool = False
    affix: str = ""
    source: str = ""
    enhance_level: int = 0
    star_level: int = 0
```

- [ ] **Step 5: Add DB schema and migration columns**

In `storage/db.py`, update the `inventory` table in `SCHEMA`:

```sql
CREATE TABLE IF NOT EXISTS inventory (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id   INTEGER NOT NULL REFERENCES players(id),
    item_id     TEXT NOT NULL,
    quantity    INTEGER NOT NULL DEFAULT 1,
    equipped    INTEGER NOT NULL DEFAULT 0,
    affix       TEXT NOT NULL DEFAULT '',
    source      TEXT NOT NULL DEFAULT '',
    enhance_level INTEGER NOT NULL DEFAULT 0,
    star_level    INTEGER NOT NULL DEFAULT 0
);
```

In `_ensure_inventory_columns`, add:

```python
if "enhance_level" not in cols:
    conn.execute("ALTER TABLE inventory ADD COLUMN enhance_level INTEGER NOT NULL DEFAULT 0")
if "star_level" not in cols:
    conn.execute("ALTER TABLE inventory ADD COLUMN star_level INTEGER NOT NULL DEFAULT 0")
```

- [ ] **Step 6: Load and save growth fields**

In `storage/repository.py`, update `_row_to_player` inventory loading:

```python
p.inventory = [
    InventoryItem(
        item_id=r["item_id"],
        quantity=r["quantity"],
        equipped=bool(r["equipped"]),
        affix=r["affix"],
        source=r["source"],
        enhance_level=r["enhance_level"],
        star_level=r["star_level"],
    )
    for r in inv_rows
]
```

Update `_save_inventory` insert:

```python
conn.execute(
    "INSERT INTO inventory (player_id,item_id,quantity,equipped,affix,source,enhance_level,star_level) "
    "VALUES (?,?,?,?,?,?,?,?)",
    (
        player.id,
        it.item_id,
        it.quantity,
        int(it.equipped),
        it.affix,
        it.source,
        it.enhance_level,
        it.star_level,
    ),
)
```

- [ ] **Step 7: Verify task tests pass**

Run:

```bash
pytest tests/test_db.py::test_init_db_adds_inventory_growth_columns_to_existing_inventory_table tests/test_repository.py::test_save_and_load_inventory_growth_fields -q
```

Expected: both tests pass.

- [ ] **Step 8: Run persistence suite**

Run:

```bash
pytest tests/test_db.py tests/test_repository.py -q
```

Expected: all DB/repository tests pass.

- [ ] **Step 9: Commit**

```bash
git add game_core/models.py storage/db.py storage/repository.py tests/test_db.py tests/test_repository.py
git commit -m "Add equipment growth persistence"
```

---

### Task 2: Add Materials and Core Equipment Progression

**Files:**
- Modify: `data/items.yaml`
- Create: `game_core/equipment_progression.py`
- Test: `tests/test_equipment_progression.py`

**Interfaces:**
- Consumes: `InventoryItem.enhance_level`, `InventoryItem.star_level`
- Produces: `MATERIAL_ITEM_IDS = {"refined_iron", "black_iron", "star_meteorite", "divine_forge_crystal"}`
- Produces: `gear_growth_stats(inv: InventoryItem, item: ItemDef) -> tuple[int, int, int]`
- Produces: `dismantle_unequipped_gear(player: Player, cfg: GameConfig, slot_filter: str = "all") -> DismantleResult`
- Produces: `enhance_equipped(player: Player, cfg: GameConfig, slot: str, times: int = 1) -> EnhanceResult`
- Produces: `star_up_equipped(player: Player, cfg: GameConfig, slot: str) -> StarUpResult`

- [ ] **Step 1: Write failing core tests**

Create `tests/test_equipment_progression.py`:

```python
from pathlib import Path
import pytest

from game_core.config import load_config
from game_core.errors import GameError, NotEnoughGold
from game_core.loot import add_item
from game_core.models import InventoryItem, Player
from game_core.equipment_progression import (
    MATERIAL_ITEM_IDS,
    dismantle_unequipped_gear,
    enhance_equipped,
    gear_growth_stats,
    star_up_equipped,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CFG = load_config(DATA_DIR)


def _player():
    return Player(group_id="g", user_id="u", name="cxh", gold=100000)


def _mat_count(player, item_id):
    return sum(inv.quantity for inv in player.inventory if inv.item_id == item_id)


def test_material_items_exist_in_config():
    assert MATERIAL_ITEM_IDS <= set(CFG.items)
    assert CFG.items["refined_iron"].slot == "consumable"
    assert CFG.items["black_iron"].slot == "consumable"
    assert CFG.items["star_meteorite"].slot == "consumable"
    assert CFG.items["divine_forge_crystal"].slot == "consumable"


def test_dismantle_skips_equipped_gear_and_grants_materials():
    p = _player()
    p.inventory = [
        InventoryItem(item_id="iron_sword", equipped=True),
        InventoryItem(item_id="iron_sword"),
        InventoryItem(item_id="fine_steel_sword"),
        InventoryItem(item_id="hp_potion", quantity=2),
    ]

    result = dismantle_unequipped_gear(p, CFG)

    assert result.dismantled_count == 2
    assert _mat_count(p, "refined_iron") == 3
    assert any(inv.item_id == "iron_sword" and inv.equipped for inv in p.inventory)
    assert _mat_count(p, "hp_potion") == 2


def test_enhance_equipped_consumes_gold_and_material():
    p = _player()
    p.inventory = [
        InventoryItem(item_id="iron_sword", equipped=True),
        InventoryItem(item_id="refined_iron", quantity=10),
    ]

    result = enhance_equipped(p, CFG, "weapon", times=1)

    sword = next(inv for inv in p.inventory if inv.item_id == "iron_sword")
    assert sword.enhance_level == 1
    assert result.success_count == 1
    assert result.gold_spent > 0
    assert p.gold == 100000 - result.gold_spent
    assert _mat_count(p, "refined_iron") == 9


def test_multi_enhance_stops_when_material_runs_out():
    p = _player()
    p.inventory = [
        InventoryItem(item_id="iron_sword", equipped=True),
        InventoryItem(item_id="refined_iron", quantity=2),
    ]

    result = enhance_equipped(p, CFG, "weapon", times=10)

    assert result.success_count == 2
    assert "材料不足" in result.stop_reason
    sword = next(inv for inv in p.inventory if inv.item_id == "iron_sword")
    assert sword.enhance_level == 2


def test_gear_growth_stats_apply_enhancement_and_stars():
    inv = InventoryItem(item_id="thunderclap_blade", enhance_level=10, star_level=2)
    item = CFG.items["thunderclap_blade"]

    atk, defense, hp = gear_growth_stats(inv, item)

    assert atk > item.atk
    assert defense == 0
    assert hp == 0


def test_star_up_uses_duplicate_item_first():
    p = _player()
    p.inventory = [
        InventoryItem(item_id="iron_sword", equipped=True),
        InventoryItem(item_id="iron_sword"),
    ]

    result = star_up_equipped(p, CFG, "weapon")

    equipped = next(inv for inv in p.inventory if inv.equipped)
    assert equipped.star_level == 1
    assert result.new_star_level == 1
    assert result.gold_spent == 2000
    assert len([inv for inv in p.inventory if inv.item_id == "iron_sword"]) == 1


def test_star_up_can_use_material_fallback():
    p = _player()
    p.inventory = [
        InventoryItem(item_id="iron_sword", equipped=True),
        InventoryItem(item_id="black_iron", quantity=3),
    ]

    result = star_up_equipped(p, CFG, "weapon")

    assert result.new_star_level == 1
    assert _mat_count(p, "black_iron") == 0


def test_enhance_rejects_missing_equipped_slot():
    p = _player()

    with pytest.raises(GameError, match="当前没有已装备"):
        enhance_equipped(p, CFG, "weapon")
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_equipment_progression.py -q
```

Expected: fail because `game_core.equipment_progression` and material config do not exist.

- [ ] **Step 3: Add material items**

Append to `data/items.yaml`:

```yaml
# ===== 材料 - 装备养成 =====
- id: refined_iron
  name: 精铁
  slot: consumable
  rarity: common
- id: black_iron
  name: 玄铁
  slot: consumable
  rarity: rare
- id: star_meteorite
  name: 星陨石
  slot: consumable
  rarity: legendary
- id: divine_forge_crystal
  name: 神铸晶
  slot: consumable
  rarity: divine
```

- [ ] **Step 4: Create progression module**

Create `game_core/equipment_progression.py`:

```python
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
    raise GameError(f"当前没有已装备的{label}。")


def _material_count(player: Player, item_id: str) -> int:
    return sum(inv.quantity for inv in player.inventory if inv.item_id == item_id)


def _consume_material(player: Player, item_id: str, quantity: int) -> None:
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
    raise GameError(f"材料不足：需要 {item_id} x{quantity}。")


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
        _grant_material(player, material.item_id, total_qty, cfg)
        result.materials[material.item_id] = result.materials.get(material.item_id, 0) + total_qty
        result.dismantled.append(DismantledGear(
            item_id=item.id,
            name=item.name,
            quantity=inv.quantity,
            materials=[MaterialCost(material.item_id, total_qty)],
        ))
    player.inventory = kept + [inv for inv in player.inventory if inv.item_id in MATERIAL_ITEM_IDS]
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
            stop_reason = f"金币不足(需 {gold_cost},当前 {player.gold})"
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
    consumed = 0
    for inv in list(player.inventory):
        if inv.equipped or inv.item_id != item_id:
            continue
        player.inventory.remove(inv)
        consumed += 1
        if consumed >= count:
            return True
    return False


def star_up_equipped(player: Player, cfg: GameConfig, slot: str) -> StarUpResult:
    inv, item = _equipped(player, cfg, slot)
    if inv.star_level >= 5:
        raise GameError("这件装备已满星。")
    old_star = inv.star_level
    target_star = old_star + 1
    gold_cost, fallback_materials = _star_cost(target_star)
    if player.gold < gold_cost:
        raise NotEnoughGold(f"金币不足(需 {gold_cost},当前 {player.gold})")
    duplicate_needed = 2 if target_star == 5 else 1
    duplicate_spent = 0
    materials_spent: dict[str, int] = {}
    if _consume_duplicate(player, item.id, duplicate_needed):
        duplicate_spent = duplicate_needed
    else:
        for cost in fallback_materials:
            if _material_count(player, cost.item_id) < cost.quantity:
                name = cfg.items[cost.item_id].name
                raise GameError(f"升星材料不足：需要同名装备 x{duplicate_needed}，或 {name} x{cost.quantity}。")
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
```

- [ ] **Step 5: Run core tests**

Run:

```bash
pytest tests/test_equipment_progression.py -q
```

Expected: all tests in `tests/test_equipment_progression.py` pass.

- [ ] **Step 6: Run config tests**

Run:

```bash
pytest tests/test_config.py tests/test_equipment_progression.py -q
```

Expected: config and progression tests pass.

- [ ] **Step 7: Commit**

```bash
git add data/items.yaml game_core/equipment_progression.py tests/test_equipment_progression.py
git commit -m "Add equipment progression core"
```

---

### Task 3: Apply Growth Stats and Update Displays

**Files:**
- Modify: `game_core/stats.py`
- Modify: `bot/formatting.py`
- Modify: `bot/inventory_image.py`
- Test: `tests/test_stats.py`
- Test: `tests/test_formatting.py`
- Test: `tests/test_inventory_image.py`

**Interfaces:**
- Consumes: `gear_growth_stats(inv, item)`
- Produces display labels `+N` and `★N` for gear with growth

- [ ] **Step 1: Write failing stats test**

Add to `tests/test_stats.py`:

```python
def test_equipment_growth_increases_player_stats_before_affixes():
    p = Player(group_id="g", user_id="u", name="cxh", level=1)
    p.inventory = [
        InventoryItem(
            item_id="iron_sword",
            equipped=True,
            enhance_level=5,
            star_level=1,
            affix='{"name":"锋锐","effects":{"atk_pct":0.2}}',
        ),
        InventoryItem(item_id="cloth_armor", equipped=True, enhance_level=5),
    ]

    assert attack(p, CFG) > 12 + CFG.items["iron_sword"].atk
    assert defense(p, CFG) > 7 + CFG.items["cloth_armor"].defense
    assert hp_max(p, CFG) > 120 + CFG.items["cloth_armor"].hp
```

- [ ] **Step 2: Write failing formatting tests**

Add to `tests/test_formatting.py`:

```python
def test_render_status_shows_equipment_growth_labels():
    p = _player()
    p.inventory = [
        InventoryItem(item_id="iron_sword", equipped=True, enhance_level=3, star_level=1),
    ]

    text = render_status(p, CFG)

    assert "+3" in text
    assert "★1" in text


def test_render_inventory_shows_material_description():
    p = _player()
    p.inventory = [InventoryItem(item_id="refined_iron", quantity=12)]

    text = render_inventory(p, CFG)

    assert "精铁" in text
    assert "材料" in text
```

Add to `tests/test_inventory_image.py`:

```python
def test_inventory_image_rows_show_equipment_growth_and_materials():
    player = _player_with_inventory([
        InventoryItem(item_id="iron_sword", equipped=True, enhance_level=3, star_level=1),
        InventoryItem(item_id="refined_iron", quantity=5),
    ])

    sections = summarize_inventory_sections(player, CFG)
    weapon = next(section for section in sections if section.title == "Weapons").rows[0]
    consumable = next(section for section in sections if section.title == "Consumables").rows[0]

    assert "+3" in weapon.name
    assert "★1" in weapon.name
    assert "材料" in consumable.stats
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
pytest tests/test_stats.py::test_equipment_growth_increases_player_stats_before_affixes tests/test_formatting.py::test_render_status_shows_equipment_growth_labels tests/test_formatting.py::test_render_inventory_shows_material_description tests/test_inventory_image.py::test_inventory_image_rows_show_equipment_growth_and_materials -q
```

Expected: fail because stats and displays do not use progression fields yet.

- [ ] **Step 4: Update stat calculations**

In `game_core/stats.py`, import growth stats:

```python
from game_core.equipment_progression import gear_growth_stats
```

Replace `_equipped_defs` with:

```python
def _equipped_items(player: Player, cfg: GameConfig):
    for inv in player.inventory:
        if inv.equipped and inv.item_id in cfg.items:
            yield inv, cfg.items[inv.item_id]
```

Update `hp_max`, `attack`, and `defense` gear bonus lines:

```python
bonus = sum(gear_growth_stats(inv, item)[2] for inv, item in _equipped_items(player, cfg))
```

```python
bonus = sum(gear_growth_stats(inv, item)[0] for inv, item in _equipped_items(player, cfg))
```

```python
bonus = sum(gear_growth_stats(inv, item)[1] for inv, item in _equipped_items(player, cfg))
```

Keep `_equipped_affixes` unchanged.

- [ ] **Step 5: Add shared display helpers**

In `bot/formatting.py`, import:

```python
from game_core.equipment_progression import MATERIAL_ITEM_IDS, gear_growth_stats
```

Add helpers near `_gear_base_stats`:

```python
def _gear_growth_label(inv) -> str:
    parts = []
    if getattr(inv, "enhance_level", 0) > 0:
        parts.append(f"+{inv.enhance_level}")
    if getattr(inv, "star_level", 0) > 0:
        parts.append(f"★{inv.star_level}")
    return " ".join(parts)


def _gear_stats_for_inventory(inv, item) -> str:
    if item is None:
        return ""
    if item.slot in ("weapon", "armor"):
        atk, defense_value, hp_value = gear_growth_stats(inv, item)
        parts = []
        if atk:
            parts.append(f"⚔️{atk:+d}")
        if defense_value:
            parts.append(f"🛡️{defense_value:+d}")
        if hp_value:
            parts.append(f"❤️{hp_value:+d}")
        return f"({' '.join(parts)})" if parts else ""
    if item.id in MATERIAL_ITEM_IDS:
        return "(材料)"
    stats = _shop_stats(item)
    return f"({stats})" if stats else ""
```

Update equipped item rendering in `render_status`:

```python
label = _gear_growth_label(i)
equipped.append(
    _item_name(cfg, i.item_id)
    + (f" {label}" if label else "")
    + stats
    + (f"[{affix}]" if affix else "")
)
```

Update `_render_inventory_with_stats` to use `_gear_stats_for_inventory(inv, item)` and append the growth label after item name.

- [ ] **Step 6: Update inventory image rows**

In `bot/inventory_image.py`, import:

```python
from game_core.equipment_progression import MATERIAL_ITEM_IDS, gear_growth_stats
```

Update `_row_for_item`:

```python
name = item.name
if item.slot in ("weapon", "armor"):
    labels = []
    if inv.enhance_level:
        labels.append(f"+{inv.enhance_level}")
    if inv.star_level:
        labels.append(f"★{inv.star_level}")
    if labels:
        name = f"{name} {' '.join(labels)}"
return InventoryImageRow(
    name=name,
    quantity=f"x{inv.quantity}",
    status="Equipped" if inv.equipped else "",
    stats=_item_stats(inv, item),
    affix=format_affix(inv.affix),
    price=str(item.price) if item.price is not None else "-",
)
```

Change `_item_stats` signature and implementation:

```python
def _item_stats(inv: InventoryItem, item: ItemDef) -> str:
    if item.slot in ("weapon", "armor"):
        atk, defense_value, hp_value = gear_growth_stats(inv, item)
    else:
        atk, defense_value, hp_value = item.atk, item.defense, item.hp
    parts: list[str] = []
    if atk:
        parts.append(f"攻击 {atk:+d}")
    if defense_value:
        parts.append(f"防御 {defense_value:+d}")
    if hp_value:
        parts.append(f"生命 {hp_value:+d}")
    if item.id in MATERIAL_ITEM_IDS:
        parts.append("材料")
    if item.heal:
        parts.append(f"回复 {item.heal}")
    if item.buff_type == "atk":
        parts.append(f"攻击 +{item.buff_value}/{item.buff_steps}步")
    elif item.buff_type == "def":
        parts.append(f"防御 +{item.buff_value}/{item.buff_steps}步")
    elif item.buff_type == "stamina":
        parts.append(f"体力 +{item.buff_value}")
    return "  ".join(parts) if parts else "-"
```

- [ ] **Step 7: Run focused display tests**

Run:

```bash
pytest tests/test_stats.py tests/test_formatting.py tests/test_inventory_image.py -q
```

Expected: focused tests pass.

- [ ] **Step 8: Commit**

```bash
git add game_core/stats.py bot/formatting.py bot/inventory_image.py tests/test_stats.py tests/test_formatting.py tests/test_inventory_image.py
git commit -m "Show equipment progression stats"
```

---

### Task 4: Add Service Layer Operations

**Files:**
- Modify: `app/services.py`
- Test: `tests/test_services_actions.py`

**Interfaces:**
- Consumes: `dismantle_unequipped_gear`, `enhance_equipped`, `star_up_equipped`
- Produces: `do_dismantle_gear(conn, cfg, group_id, user_id, slot_filter)`
- Produces: `do_enhance_equipped(conn, cfg, group_id, user_id, slot_query, times, now)`
- Produces: `do_star_up_equipped(conn, cfg, group_id, user_id, slot_query, now)`

- [ ] **Step 1: Write failing service tests**

Add to `tests/test_services_actions.py`:

```python
def test_do_dismantle_gear_persists_materials_and_keeps_equipped():
    conn = _conn()
    p = _create_player(conn, gold=0)
    p.inventory = [
        InventoryItem(item_id="iron_sword", equipped=True),
        InventoryItem(item_id="iron_sword"),
        InventoryItem(item_id="fine_steel_sword"),
    ]
    repo.save_player(conn, p)

    result, updated = services.do_dismantle_gear(conn, CFG, "g", "u", "all")

    assert result.dismantled_count == 2
    assert any(inv.item_id == "iron_sword" and inv.equipped for inv in updated.inventory)
    assert sum(inv.quantity for inv in updated.inventory if inv.item_id == "refined_iron") == 3


def test_do_enhance_equipped_persists_level_and_spends_resources():
    conn = _conn()
    p = _create_player(conn, gold=10000)
    p.inventory = [
        InventoryItem(item_id="iron_sword", equipped=True),
        InventoryItem(item_id="refined_iron", quantity=5),
    ]
    repo.save_player(conn, p)

    result = services.do_enhance_equipped(conn, CFG, "g", "u", "武器", 2, now=1000)

    loaded = repo.get_player(conn, "g", "u")
    sword = next(inv for inv in loaded.inventory if inv.item_id == "iron_sword")
    assert result.success_count == 2
    assert sword.enhance_level == 2
    assert loaded.gold < 10000


def test_do_star_up_equipped_persists_star_and_consumes_duplicate():
    conn = _conn()
    p = _create_player(conn, gold=10000)
    p.inventory = [
        InventoryItem(item_id="iron_sword", equipped=True),
        InventoryItem(item_id="iron_sword"),
    ]
    repo.save_player(conn, p)

    result = services.do_star_up_equipped(conn, CFG, "g", "u", "武器", now=1000)

    loaded = repo.get_player(conn, "g", "u")
    sword = next(inv for inv in loaded.inventory if inv.equipped)
    assert result.new_star_level == 1
    assert sword.star_level == 1
    assert len([inv for inv in loaded.inventory if inv.item_id == "iron_sword"]) == 1
```

If this test file uses different helper names, adapt only the helper calls, not the service assertions.

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_services_actions.py::test_do_dismantle_gear_persists_materials_and_keeps_equipped tests/test_services_actions.py::test_do_enhance_equipped_persists_level_and_spends_resources tests/test_services_actions.py::test_do_star_up_equipped_persists_star_and_consumes_duplicate -q
```

Expected: fail because service functions do not exist.

- [ ] **Step 3: Add service imports and dataclasses**

In `app/services.py`, import:

```python
from game_core.equipment_progression import (
    DismantleResult,
    EnhanceResult,
    StarUpResult,
    dismantle_unequipped_gear,
    enhance_equipped,
    star_up_equipped,
)
```

No new result dataclasses are needed if the core dataclasses are returned directly.

- [ ] **Step 4: Generalize gear slot parser**

Change `_parse_gear_slot` in `app/services.py` so the error text can be reused:

```python
def _parse_gear_slot(slot_query: str, *, usage: str = "用法:重铸 武器/装备 [次数]") -> str:
    text = str(slot_query).strip()
    if text in {"武器", "weapon"}:
        return "weapon"
    if text in {"装备", "防具", "armor"}:
        return "armor"
    raise GameError(usage)
```

Update existing `do_reforge_equipped` call:

```python
slot = _parse_gear_slot(slot_query, usage="用法:重铸 武器/装备 [次数]")
```

- [ ] **Step 5: Add service functions**

Add below `do_sell_unequipped_gear`:

```python
def do_dismantle_gear(conn, cfg, group_id, user_id, slot_filter="all"):
    p = _require(conn, cfg, group_id, user_id)
    if slot_filter not in {"all", "weapon", "armor"}:
        raise GameError("分解目标只能是 装备、武器 或 防具。")
    result = dismantle_unequipped_gear(p, cfg, slot_filter)
    if result.dismantled_count <= 0:
        raise GameError("没有可分解的未装备武器或防具。")
    repo.save_player(conn, p)
    return result, p


def do_enhance_equipped(conn, cfg, group_id, user_id, slot_query, times=1, now=None):
    p = _require(conn, cfg, group_id, user_id)
    slot = _parse_gear_slot(slot_query, usage="用法:强化 武器/装备 [次数]")
    requested = max(1, int(times))
    result = enhance_equipped(p, cfg, slot, requested)
    if now is not None:
        p.last_active_at = now
    repo.save_player(conn, p)
    result.player = p if hasattr(result, "player") else p
    return result


def do_star_up_equipped(conn, cfg, group_id, user_id, slot_query, now=None):
    p = _require(conn, cfg, group_id, user_id)
    slot = _parse_gear_slot(slot_query, usage="用法:升星 武器/装备")
    result = star_up_equipped(p, cfg, slot)
    if now is not None:
        p.last_active_at = now
    repo.save_player(conn, p)
    result.player = p if hasattr(result, "player") else p
    return result
```

If assigning `player` to core dataclasses is undesirable, add `player: Player | None = None` to `EnhanceResult` and `StarUpResult` in Task 2 before using it in bot formatting.

- [ ] **Step 6: Run service tests**

Run:

```bash
pytest tests/test_services_actions.py -q
```

Expected: service action tests pass.

- [ ] **Step 7: Commit**

```bash
git add app/services.py tests/test_services_actions.py game_core/equipment_progression.py
git commit -m "Add equipment progression services"
```

---

### Task 5: Add Result Formatting, Commands, and Fuzzy Routing

**Files:**
- Modify: `bot/formatting.py`
- Modify: `bot/fuzzy_commands.py`
- Modify: `bot/plugins/rpg.py`
- Test: `tests/test_formatting.py`
- Test: `tests/test_fuzzy_commands.py`

**Interfaces:**
- Consumes: `services.do_dismantle_gear`
- Consumes: `services.do_enhance_equipped`
- Consumes: `services.do_star_up_equipped`
- Produces: OneBot commands `分解装备`, `强化`, `升星`

- [ ] **Step 1: Write failing formatting tests**

Add to `tests/test_formatting.py`:

```python
from game_core.equipment_progression import (
    DismantledGear,
    DismantleResult,
    EnhanceResult,
    MaterialCost,
    StarUpResult,
)


def test_render_dismantle_result_lists_materials():
    result = DismantleResult(
        dismantled=[
            DismantledGear(
                item_id="iron_sword",
                name="铁剑",
                quantity=2,
                materials=[MaterialCost("refined_iron", 2)],
            )
        ],
        materials={"refined_iron": 2},
    )

    text = render_dismantle_result(result, CFG)

    assert "分解完成" in text
    assert "铁剑" in text
    assert "精铁" in text


def test_render_enhance_and_star_up_results():
    enhance = EnhanceResult(
        item_name="铁剑",
        slot="weapon",
        old_level=1,
        new_level=3,
        requested=2,
        success_count=2,
        gold_spent=100,
        materials_spent={"refined_iron": 2},
    )
    star = StarUpResult(
        item_name="铁剑",
        slot="weapon",
        old_star_level=0,
        new_star_level=1,
        gold_spent=2000,
        duplicate_spent=1,
    )

    assert "强化结算" in render_enhance_result(enhance, CFG)
    assert "+1 -> +3" in render_enhance_result(enhance, CFG)
    assert "升星成功" in render_star_up_result(star, CFG)
    assert "★0 -> ★1" in render_star_up_result(star, CFG)
```

- [ ] **Step 2: Write failing fuzzy command tests**

Add to `tests/test_fuzzy_commands.py`:

```python
def test_equipment_progression_commands_are_supported():
    assert_parsed("分解装备", "dismantle_gear", "all")
    assert_parsed("一键分解装备", "dismantle_gear", "all")
    assert_parsed("分解武器", "dismantle_gear", "weapon")
    assert_parsed("分解防具", "dismantle_gear", "armor")
    assert_parsed("强化 武器 10", "enhance_gear", "武器 10")
    assert_parsed("强化武器10", "enhance_gear", "武器 10")
    assert_parsed("升星 装备", "star_up_gear", "装备")


def test_spend_progression_commands_require_explicit_action_words():
    assert parse_fuzzy_command("武器强化吗") is None
    assert parse_fuzzy_command("装备升星材料在哪") is None
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
pytest tests/test_formatting.py::test_render_dismantle_result_lists_materials tests/test_formatting.py::test_render_enhance_and_star_up_results tests/test_fuzzy_commands.py::test_equipment_progression_commands_are_supported tests/test_fuzzy_commands.py::test_spend_progression_commands_require_explicit_action_words -q
```

Expected: fail because renderers and fuzzy routes do not exist.

- [ ] **Step 4: Add formatting functions**

In `bot/formatting.py`, add:

```python
def _material_name(cfg: GameConfig, item_id: str) -> str:
    item = cfg.items.get(item_id)
    return item.name if item else item_id


def _format_materials(materials: dict[str, int], cfg: GameConfig) -> str:
    return "、".join(
        f"{_material_name(cfg, item_id)} x{qty}"
        for item_id, qty in materials.items()
        if qty > 0
    ) or "无"


def render_dismantle_result(result, cfg: GameConfig) -> str:
    lines = ["🧰 分解完成", f"分解 {result.dismantled_count} 件装备："]
    for entry in result.dismantled:
        material_text = "、".join(
            f"{_material_name(cfg, cost.item_id)} x{cost.quantity}"
            for cost in entry.materials
        )
        lines.append(f"· {entry.name} x{entry.quantity} -> {material_text}")
    lines.append("")
    lines.append("获得材料：" + _format_materials(result.materials, cfg))
    return "\n".join(lines)


def render_enhance_result(result, cfg: GameConfig) -> str:
    title = "🔨 强化结算" if result.success_count != 1 else "🔨 强化成功"
    lines = [
        title,
        f"{result.item_name} +{result.old_level} -> +{result.new_level}",
        f"消耗：金币 {result.gold_spent}，{_format_materials(result.materials_spent, cfg)}",
    ]
    if result.stop_reason:
        lines.append(f"停止原因：{result.stop_reason}")
    return "\n".join(lines)


def render_star_up_result(result, cfg: GameConfig) -> str:
    spent = []
    if result.duplicate_spent:
        spent.append(f"同名装备 x{result.duplicate_spent}")
    material_text = _format_materials(result.materials_spent, cfg)
    if material_text != "无":
        spent.append(material_text)
    spent.append(f"金币 {result.gold_spent}")
    return "\n".join([
        "⭐ 升星成功",
        f"{result.item_name} ★{result.old_star_level} -> ★{result.new_star_level}",
        "消耗：" + "，".join(spent),
    ])
```

- [ ] **Step 5: Add fuzzy routes**

In `bot/fuzzy_commands.py`, add rules before generic `equip`, `use`, and `buy` rules:

```python
_AliasRule("dismantle_gear", "一键分解装备", no_arg_only=True, fuzzy=False, fixed_arg="all"),
_AliasRule("dismantle_gear", "分解装备", no_arg_only=True, fuzzy=False, fixed_arg="all"),
_AliasRule("dismantle_gear", "分解武器", no_arg_only=True, fuzzy=False, fixed_arg="weapon"),
_AliasRule("dismantle_gear", "分解防具", no_arg_only=True, fuzzy=False, fixed_arg="armor"),
_AliasRule("enhance_gear", "强化", requires_arg=True, fuzzy=False),
_AliasRule("star_up_gear", "升星", requires_arg=True, fuzzy=False),
```

In `_normalize_arg`, add:

```python
if command == "enhance_gear":
    match = _TRAILING_NUMBER_RE.match(arg)
    if match:
        arg = f"{match.group(1).strip()} {match.group(2)}"
```

In `_is_allowed_arg`, add:

```python
if rule.command in {"enhance_gear", "star_up_gear"} and not arg.startswith(
    ("武器", "装备", "防具", "weapon", "armor")
):
    return False
```

- [ ] **Step 6: Add OneBot commands**

In `bot/plugins/rpg.py`, import new renderers:

```python
render_dismantle_result,
render_enhance_result,
render_star_up_result,
```

Add commands before world Boss commands:

```python
cmd_dismantle_gear = on_command(
    "分解装备",
    aliases={"一键分解装备", "分解武器", "分解防具"},
    rule=to_me(),
    priority=10,
    block=True,
)


def _dismantle_filter_from_text(text: str) -> str:
    if "武器" in text:
        return "weapon"
    if "防具" in text:
        return "armor"
    return "all"


@cmd_dismantle_gear.handle()
async def handle_dismantle_gear(bot: Bot, event: Event):
    gid, uid = _scope(event)

    async def _do():
        async with state.player_lock(gid, uid):
            result, p = services.do_dismantle_gear(
                state.conn(), state.CFG, gid, uid,
                _dismantle_filter_from_text(event.get_plaintext()),
            )
            await _reply_to(bot, event, p.name, render_dismantle_result(result, state.CFG))

    await _guard(bot, event, _do())
```

Add helpers and handlers:

```python
def _parse_slot_count_arg(arg: str) -> tuple[str, int]:
    parts = str(arg).split()
    if not parts:
        return "", 1
    if len(parts) == 1:
        return parts[0], 1
    return parts[0], int(parts[1])


cmd_enhance_gear = on_command("强化", rule=to_me(), priority=10, block=True)


async def _handle_enhance_gear_arg(bot: Bot, event: Event, arg: str):
    try:
        slot_query, times = _parse_slot_count_arg(arg)
    except ValueError:
        await _reply(bot, event, "次数必须是正整数")
        return
    gid, uid = _scope(event)

    async def _do():
        async with state.player_lock(gid, uid):
            result = services.do_enhance_equipped(
                state.conn(), state.CFG, gid, uid, slot_query, times, state.now()
            )
            p = repo.get_player(state.conn(), gid, uid)
            await _reply_to(bot, event, p.name, render_enhance_result(result, state.CFG))

    await _guard(bot, event, _do())


@cmd_enhance_gear.handle()
async def handle_enhance_gear(bot: Bot, event: Event):
    await _handle_enhance_gear_arg(bot, event, _arg(event, "强化"))
```

Add star-up:

```python
cmd_star_up_gear = on_command("升星", rule=to_me(), priority=10, block=True)


async def _handle_star_up_gear_arg(bot: Bot, event: Event, arg: str):
    gid, uid = _scope(event)

    async def _do():
        async with state.player_lock(gid, uid):
            result = services.do_star_up_equipped(
                state.conn(), state.CFG, gid, uid, arg, state.now()
            )
            p = repo.get_player(state.conn(), gid, uid)
            await _reply_to(bot, event, p.name, render_star_up_result(result, state.CFG))

    await _guard(bot, event, _do())


@cmd_star_up_gear.handle()
async def handle_star_up_gear(bot: Bot, event: Event):
    await _handle_star_up_gear_arg(bot, event, _arg(event, "升星"))
```

Update `handle_fuzzy`:

```python
elif parsed.command == "dismantle_gear":
    gid, uid = _scope(event)
    async def _do():
        async with state.player_lock(gid, uid):
            result, p = services.do_dismantle_gear(
                state.conn(), state.CFG, gid, uid, parsed.arg or "all"
            )
            await _reply_to(bot, event, p.name, render_dismantle_result(result, state.CFG))
    await _guard(bot, event, _do())
elif parsed.command == "enhance_gear":
    await _handle_enhance_gear_arg(bot, event, parsed.arg)
elif parsed.command == "star_up_gear":
    await _handle_star_up_gear_arg(bot, event, parsed.arg)
```

- [ ] **Step 7: Run command tests**

Run:

```bash
pytest tests/test_formatting.py tests/test_fuzzy_commands.py tests/test_onebot_only_architecture.py -q
```

Expected: formatting, fuzzy routing, and OneBot-only architecture tests pass.

- [ ] **Step 8: Commit**

```bash
git add bot/formatting.py bot/fuzzy_commands.py bot/plugins/rpg.py tests/test_formatting.py tests/test_fuzzy_commands.py
git commit -m "Add equipment progression commands"
```

---

### Task 6: Add Material Reward Hooks and Command Documentation

**Files:**
- Modify: `app/services.py`
- Modify: `game_core/world_boss.py`
- Modify: `game_core/void_sacrifice.py`
- Modify: `docs/game-commands.md`
- Test: `tests/test_world_boss_core.py`
- Test: `tests/test_void_sacrifice_core.py`
- Test: `tests/test_formatting.py`

**Interfaces:**
- Consumes: material item IDs from `game_core.equipment_progression`
- Produces: world Boss and void sacrifice can grant material items

- [ ] **Step 1: Write failing material reward tests**

Add to `tests/test_world_boss_core.py`:

```python
def test_world_boss_rewards_can_include_upgrade_materials():
    seen_material = False
    for seed in range(100):
        reward = roll_world_boss_rewards(
            0.5, player_level=30, active_player_count=3, cfg=CFG, rng=random.Random(seed)
        )
        if any(item_id in {"star_meteorite", "divine_forge_crystal"} for item_id, _ in reward.consumables):
            seen_material = True
            break

    assert seen_material
```

Add to `tests/test_void_sacrifice_core.py`:

```python
def test_ten_draw_void_sacrifice_can_return_upgrade_materials():
    seen_material = False
    for seed in range(100):
        roll = roll_void_sacrifice(10, CFG, random.Random(seed), VoidSacrificePity())
        if any(draw.consumable_id in {"black_iron", "star_meteorite"} for draw in roll.draws):
            seen_material = True
            break

    assert seen_material
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_world_boss_core.py::test_world_boss_rewards_can_include_upgrade_materials tests/test_void_sacrifice_core.py::test_ten_draw_void_sacrifice_can_return_upgrade_materials -q
```

Expected: fail because reward pools do not include materials.

- [ ] **Step 3: Add materials to reward pools**

In `game_core/world_boss.py`, add material IDs to `CONSUMABLE_REWARD_POOL` or equivalent reward pool:

```python
CONSUMABLE_REWARD_POOL = [
    "hp_potion",
    "greater_hp_potion",
    "supreme_hp_potion",
    "atk_potion_major",
    "def_potion_major",
    "black_iron",
    "star_meteorite",
    "divine_forge_crystal",
]
```

In `game_core/void_sacrifice.py`, add material IDs to the common consumable pool:

```python
COMMON_CONSUMABLE_POOL = [
    "hp_potion",
    "greater_hp_potion",
    "supreme_hp_potion",
    "atk_potion_major",
    "def_potion_major",
    "stamina_potion",
    "refined_iron",
    "black_iron",
    "star_meteorite",
]
```

Keep `divine_forge_crystal` out of normal void common rolls unless later balance requires it.

- [ ] **Step 4: Ensure service reward grants already work**

Do not add special service code if materials are already granted through existing `_loot.add_item()` consumable paths in `do_void_sacrifice()` and `_world_boss_rewards()`. Verify by reading those functions and confirming they call `_loot.add_item(player, item_id, qty=qty, cfg=cfg, rng=rng)`.

- [ ] **Step 5: Document commands**

In `docs/game-commands.md`, add:

```markdown
## 装备养成

### 分解装备

指令：
- `分解装备`
- `分解武器`
- `分解防具`
- `一键分解装备`

预期输出：

```text
「cxh」
🧰 分解完成
分解 2 件装备：
· 铁剑 x1 -> 精铁 x1

获得材料：精铁 x1
```

### 强化

指令：
- `强化 武器`
- `强化 装备`
- `强化 武器 10`

预期输出：

```text
「cxh」
🔨 强化成功
霹雳斩马刀 +11 -> +12
消耗：金币 1488，玄铁 x1
```

### 升星

指令：
- `升星 武器`
- `升星 装备`

预期输出：

```text
「cxh」
⭐ 升星成功
霹雳斩马刀 ★1 -> ★2
消耗：同名装备 x1，金币 5000
```
```

If nested code fences break the markdown during editing, use indented code blocks under this section instead.

- [ ] **Step 6: Run focused reward/docs tests**

Run:

```bash
pytest tests/test_world_boss_core.py tests/test_void_sacrifice_core.py -q
```

Expected: focused reward tests pass.

- [ ] **Step 7: Commit**

```bash
git add game_core/world_boss.py game_core/void_sacrifice.py docs/game-commands.md tests/test_world_boss_core.py tests/test_void_sacrifice_core.py
git commit -m "Add equipment material rewards"
```

---

### Task 7: Final Verification and Balance Smoke Test

**Files:**
- Test-only verification across repo.

**Interfaces:**
- Consumes all previous tasks.
- Produces final confidence before push or merge.

- [ ] **Step 1: Run full test suite**

Run:

```bash
pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run a manual progression smoke script**

Run:

```bash
python -c "from pathlib import Path; from game_core.config import load_config; from game_core.models import Player, InventoryItem; from game_core.equipment_progression import dismantle_unequipped_gear, enhance_equipped, star_up_equipped; from game_core.stats import attack; cfg=load_config(Path('data')); p=Player(group_id='g', user_id='u', name='cxh', gold=100000); p.inventory=[InventoryItem(item_id='iron_sword', equipped=True), InventoryItem(item_id='iron_sword'), InventoryItem(item_id='fine_steel_sword'), InventoryItem(item_id='black_iron', quantity=10)]; before=attack(p,cfg); d=dismantle_unequipped_gear(p,cfg); e=enhance_equipped(p,cfg,'weapon',2); s=star_up_equipped(p,cfg,'weapon'); after=attack(p,cfg); print(before, after, d.dismantled_count, e.success_count, s.new_star_level)"
```

Expected: output shows `after > before`, dismantled count at least `1`, enhancement success at least `1`, and star level `1`.

- [ ] **Step 3: Inspect git status**

Run:

```bash
git status --short --branch
```

Expected: branch is clean after task commits, or only intentional documentation changes remain.

- [ ] **Step 4: Commit any final documentation-only corrections**

If `docs/game-commands.md` or plan checkboxes were updated during execution:

```bash
git add docs/game-commands.md docs/superpowers/plans/2026-07-02-equipment-progression.md
git commit -m "Document equipment progression rollout"
```

Expected: commit created only if there are documentation changes.

---

## Self-Review

Spec coverage:

- Enhancement levels: Task 2 core, Task 3 stats/display, Task 4 services, Task 5 commands.
- Star levels: Task 2 core, Task 3 stats/display, Task 4 services, Task 5 commands.
- Gear dismantling into materials: Task 2 core, Task 4 services, Task 5 commands.
- New material items: Task 2 config.
- Display changes: Task 3 and Task 5 result rendering.
- OneBot commands: Task 5.
- Reward sources from world Boss and void sacrifice: Task 6.
- Tests: each task includes failing tests, verification commands, and commit steps.

Placeholder scan:

- No flagged planning-red-flag terms or open-ended validation steps remain.
- Steps that change code include concrete snippets or exact edit instructions.

Type consistency:

- `InventoryItem.enhance_level` and `InventoryItem.star_level` are introduced in Task 1 before use.
- `gear_growth_stats`, `dismantle_unequipped_gear`, `enhance_equipped`, and `star_up_equipped` are introduced in Task 2 before services and display consume them.
- Service names in Task 4 match command usage in Task 5.
