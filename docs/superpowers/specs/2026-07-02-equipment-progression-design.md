# Equipment Progression Design

## Goal

Add an equipment-centered growth loop so players can keep improving even when they do not immediately find a better weapon or armor piece.

The loop is:

```text
Explore / sacrifice / world Boss -> get gear -> keep useful gear -> dismantle extras
-> upgrade or star-up equipped gear -> gain stats -> push deeper floors
```

This should support dungeon expansion beyond floor 100 without making progression depend only on random drops.

## Scope

This design covers:

- Equipment enhancement levels.
- Equipment star levels.
- Gear dismantling into materials.
- New material items.
- Commands for enhancement, star-up, and dismantling.
- Display changes for status, inventory text, and inventory image output.

This design does not cover:

- New floors or new monsters.
- New affix pools.
- Character realm breakthrough.
- Monster collection or mastery systems.

## Core Rules

- Only weapons and armor can be enhanced or starred.
- Enhancement and star-up apply to the player's currently equipped weapon or armor.
- Existing gear remains valid; gear with no enhancement fields should behave as level `0`, star `0`.
- Enhancement is stable, repeatable growth with moderate cost.
- Star-up is expensive long-term growth with larger percentage gains.
- Dismantling only affects unequipped weapons and armor.
- Selling unequipped gear remains available; dismantling becomes an alternative choice.
- Gear affixes remain independent and continue to apply as they do today.

## New Material Items

Add four consumable-like material items. They are not directly usable by players, but appear in inventory and are consumed by upgrade systems.

| Material | Main Source | Main Use |
|---|---|---|
| `refined_iron` / 精铁 | common, uncommon gear dismantle | Low-tier enhancement |
| `black_iron` / 玄铁 | rare, epic gear dismantle | Mid-tier enhancement and low star-up |
| `star_meteorite` / 星陨石 | legendary, mythic gear dismantle, world Boss | High-tier enhancement and star-up |
| `divine_forge_crystal` / 神铸晶 | divine gear dismantle, world Boss, void sacrifice pity byproduct | High-star star-up |

Materials use `slot: consumable` for storage compatibility, but should be excluded from `使用` command effects unless a future crafting feature needs them.

## Dismantling

### Commands

- `分解装备`: dismantle all unequipped weapons and armor.
- `分解武器`: dismantle all unequipped weapons.
- `分解防具`: dismantle all unequipped armor.
- `一键分解装备`: alias of `分解装备`.

Fuzzy command routing can support natural variants such as `分解背包装备`, `分解多余武器`, and `清理成材料`.

### Dismantle Rewards

Recommended base material output:

| Gear Rarity | Material |
|---|---|
| common | 精铁 x1 |
| uncommon | 精铁 x2 |
| rare | 玄铁 x1 |
| epic | 玄铁 x2 |
| legendary | 星陨石 x1 |
| mythic | 星陨石 x2 |
| divine | 神铸晶 x1 |

Additional rules:

- Gear with enhancement levels returns part of its invested materials, recommended `35%`.
- Gear with star levels returns part of its invested star materials, recommended `25%`.
- Dismantling never returns gold.
- Equipped gear is never dismantled by batch commands.

### Example Output

```text
「cxh」
🧰 分解完成
分解 8 件装备：
· 铁剑 x2 -> 精铁 x2
· 百炼钢剑 x1 -> 精铁 x2
· 月纹钢剑 x1 -> 玄铁 x1

获得材料：
精铁 x4
玄铁 x1
```

If nothing can be dismantled:

```text
没有可分解的未装备武器或防具。
```

## Enhancement

### Commands

- `强化 武器`: enhance equipped weapon once.
- `强化 装备`: enhance equipped armor once.
- `强化 防具`: alias of `强化 装备`.
- `强化 武器 10`: attempt up to 10 weapon enhancements.
- `强化 装备 10`: attempt up to 10 armor enhancements.

If the player lacks gold or materials during multi-enhance, stop at the last successful enhancement and report both success count and blocking reason.

### Enhancement Caps

| Rarity | Max Enhancement |
|---|---:|
| common | +5 |
| uncommon | +8 |
| rare | +12 |
| epic | +16 |
| legendary | +20 |
| mythic | +25 |
| divine | +30 |

### Enhancement Stat Gain

Each enhancement level increases the gear's base stats by `4%`.

Rules:

- Weapon attack grows by at least `+1 atk` per enhancement level if the weapon has attack.
- Armor defense grows by at least `+1 def` per enhancement level if the armor has defense.
- HP-bearing gear also increases HP.
- Negative base stats also scale by level. For example, a hidden weapon with negative defense becomes more aggressive but also more fragile as it is enhanced.

Recommended formula:

```text
enhanced_stat = base_stat + sign(base_stat) * max(1, floor(abs(base_stat) * 0.04 * enhance_level))
```

For zero base stats, the stat remains zero.

### Enhancement Cost

Cost scales by target level and rarity.

Recommended formula:

```text
target_level = current_enhance + 1
gold_cost = floor(base_price_or_floor * rarity_multiplier * (1 + target_level * 0.18))
```

Use `base_price_or_floor`:

- If item has `price`, use item price.
- If item has no price, use a rarity floor:
  - legendary: `3000`
  - mythic: `6000`
  - divine: `12000`

Recommended rarity multiplier:

| Rarity | Multiplier |
|---|---:|
| common | 0.25 |
| uncommon | 0.35 |
| rare | 0.50 |
| epic | 0.75 |
| legendary | 1.00 |
| mythic | 1.35 |
| divine | 1.80 |

Recommended material cost by target level:

| Target Level | Material Cost |
|---|---|
| 1-8 | 精铁 x1 |
| 9-16 | 玄铁 x1 |
| 17-24 | 星陨石 x1 |
| 25-30 | 神铸晶 x1 |

For mythic and divine gear, require at least 玄铁 for early enhancement:

- mythic level 1-8: 玄铁 x1 instead of 精铁.
- divine level 1-8: 星陨石 x1 instead of 精铁.

### Example Output

```text
「cxh」
🔨 强化成功：霹雳斩马刀 +11 -> +12
消耗：金币 1488，玄铁 x1
当前属性：攻击 +116 -> +171
```

For multi-enhance:

```text
「cxh」
🔨 强化结算：武器成功 4 次
霹雳斩马刀 +8 -> +12
总消耗：金币 5120，玄铁 x4
停止原因：玄铁不足
```

## Star-Up

### Commands

- `升星 武器`: star-up equipped weapon once.
- `升星 装备`: star-up equipped armor once.
- `升星 防具`: alias of `升星 装备`.

No multi-star command in the first version. Star-up is expensive and should stay explicit.

### Star Cap and Stat Gain

Each gear piece can reach at most 5 stars.

| Star | Total Bonus |
|---|---:|
| 1 | +8% |
| 2 | +16% |
| 3 | +25% |
| 4 | +35% |
| 5 | +50% |

Star bonus multiplies the gear's enhanced stats, not the player's total stats.

Recommended formula:

```text
gear_stat_after_growth = enhanced_stat * (1 + star_bonus)
```

Affixes then apply as they currently do at the player-stat layer.

### Star-Up Cost

Star-up should consume gold, materials, and either a duplicate item or universal high-tier material.

Recommended requirements:

| Target Star | Gold | Main Requirement |
|---|---:|---|
| 1 | 2000 | same item x1 or 玄铁 x3 |
| 2 | 5000 | same item x1 or 玄铁 x6 |
| 3 | 10000 | same item x1 + 星陨石 x1, or 星陨石 x4 |
| 4 | 20000 | same item x1 + 星陨石 x3, or 神铸晶 x1 + 星陨石 x5 |
| 5 | 40000 | same item x2 + 神铸晶 x1, or 神铸晶 x3 |

The duplicate item must be unequipped and have the same `item_id`. Its own enhancement/star state does not transfer, but dismantle refund rules do not apply when it is consumed for star-up.

### Example Output

```text
「Crazy」
⭐ 升星成功：锁魂钉 ★1 -> ★2
消耗：金币 5000，同名装备 x1
星级加成：+8% -> +16%
```

If the player lacks duplicates and materials:

```text
升星材料不足：需要同名装备 x1，或 玄铁 x6。
```

## Stat Calculation Order

Stat calculation should be deterministic and easy to reason about.

Recommended order:

1. Start with item base stats from config.
2. Apply enhancement bonus.
3. Apply star bonus.
4. Add resulting gear stats to player base stats.
5. Apply affix percentage modifiers to final player stats.
6. Apply temporary buffs and overdrive penalties using the existing behavior.

This keeps enhancement/star-up as gear growth, while affixes remain character-level percentage modifiers.

## Data Model

Add fields to inventory items:

- `enhance_level`: integer, default `0`.
- `star_level`: integer, default `0`.

Database migration:

- Add `enhance_level INTEGER NOT NULL DEFAULT 0` to `inventory`.
- Add `star_level INTEGER NOT NULL DEFAULT 0` to `inventory`.

In-memory model:

```python
InventoryItem(
    item_id: str,
    quantity: int = 1,
    equipped: bool = False,
    affix: str = "",
    source: str = "",
    enhance_level: int = 0,
    star_level: int = 0,
)
```

Repository load/save must round-trip both fields.

## Display Changes

Equipped status should show enhancement and star state:

```text
凤羽宝衣 +6 ★1[轻盈(防御+11% 生命+12%)]
霹雳斩马刀 +12 ★2[锋锐(攻击+13%)]
```

Backpack text and inventory images should show:

- Gear name.
- Quantity.
- Equipped state.
- Enhancement level.
- Star level.
- Current computed gear stats.
- Affix text.

Materials should display as consumable/material rows:

```text
精铁 x12  材料：低级强化
玄铁 x3   材料：中级强化/升星
```

## Service Layer

Add service functions:

- `do_dismantle_gear(conn, cfg, group_id, user_id, slot_filter)`.
- `do_enhance_equipped(conn, cfg, group_id, user_id, slot, times, now)`.
- `do_star_up_equipped(conn, cfg, group_id, user_id, slot, now)`.

Each service should:

- Load player by `group_id` and `user_id`.
- Validate the target equipped gear.
- Validate cost and materials.
- Mutate player inventory and gold.
- Save in one transaction.
- Return structured result objects for formatting.

## Bot Commands

Add OneBot commands:

- `分解装备`, aliases `一键分解装备`, `分解防具`, `分解武器`.
- `强化`, with argument parser for `武器/装备/防具` and optional count.
- `升星`, with argument parser for `武器/装备/防具`.

Fuzzy parser should route common variants but avoid accidental spend actions. For `强化` and `升星`, require the user text to clearly contain the action word.

## Error Handling

Recommended errors:

- No character: reuse existing no-character prompt.
- No equipped gear: `当前没有已装备的武器。`
- Invalid slot: `目标只能是 武器 或 装备。`
- Enhancement at cap: `这件装备已达到强化上限。`
- Star at cap: `这件装备已满星。`
- Not enough gold: `金币不足(需 X，当前 Y)。`
- Not enough material: `材料不足：需要 精铁 x1。`
- No dismantle targets: `没有可分解的未装备武器或防具。`

Batch enhancement should report partial success instead of treating later shortage as a total failure.

## Balance Intent

The first implementation should make equipment progression meaningful but not mandatory at shallow floors.

Recommended targets:

- Floor 1-60: natural drops and levels are enough.
- Floor 60-100: enhancement helps smooth bad luck.
- Floor 100+: enhancement and star-up become expected progression.
- A player should feel visible progress after a few dismantle/enhance cycles.
- Full divine +30 ★5 should be aspirational and expensive, not required for floor 100.

## Tests

Add focused tests for:

- Database migration preserves old inventory rows with default enhancement/star values.
- Repository round-trips `enhance_level` and `star_level`.
- Dismantling skips equipped gear and grants correct materials.
- Enhancement consumes gold/materials and updates stats.
- Multi-enhance stops cleanly on cap or shortage.
- Star-up consumes duplicate gear or fallback materials.
- Stats calculation applies base -> enhancement -> stars -> affixes in order.
- Status and inventory render enhancement/star labels.
- Inventory image rows include enhancement/star information.
- Fuzzy commands route dismantle/enhance/star-up variants.

## Rollout Notes

- Existing players get `enhance_level = 0` and `star_level = 0` automatically.
- Existing high-tier equipment remains valuable because it can now be enhanced and starred.
- The current one-click sell command should remain unchanged.
- It may be useful to add a help-menu note: `多余装备可出售换金币，也可分解换强化材料。`
