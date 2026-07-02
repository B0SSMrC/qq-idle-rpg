# Void Sacrifice Design

## Goal

Add `虚空献祭` as a mid-to-late-game gold sink and gear lottery. Players spend gold for one draw or ten draws, with a chance to receive rare weapons and armor. The system should feel exciting without flooding inventories or replacing exploration and world Boss rewards.

## Commands

Supported commands:

```text
虚空献祭
献祭
虚空献祭 10
献祭 10
十连献祭
献祭十连
```

Rules:

- No argument means one draw.
- Only `1` and `10` are valid draw counts.
- Group messages still follow the existing OneBot rule: the bot must be mentioned in group chats.
- Fuzzy command routing may support natural variants such as `来一次献祭`, but spend actions must stay explicit enough to avoid accidental gold loss.

## Cost

```text
1 draw: 1000 gold
10 draws: 10000 gold
```

Gold is deducted before rolling rewards and all rewards are granted in the same service call. If the player does not have enough gold, nothing is deducted.

## Base Rates

Each normal draw uses this rarity table:

| Result | Chance |
| --- | ---: |
| Common feedback | 50.0% |
| Rare gear | 25.0% |
| Epic gear | 15.0% |
| Legendary gear | 7.0% |
| Mythic gear | 2.5% |
| Divine gear | 0.5% |

Common feedback does not grant gear. It grants one of:

- A small gold refund, recommended range `120-320`.
- One consumable from `金疮药`, `续命丹`, `九转还魂丹`, `虎骨酒`, `金钟罩符`, or `回气丹`.

This keeps the draw from filling the backpack with low-value equipment while still giving a visible result.

## Ten-Draw Guarantee

A ten-draw must contain at least one `epic+` reward.

If the first nine draws and the natural tenth draw contain no `epic`, `legendary`, `mythic`, or `divine` gear, the tenth reward is upgraded to `epic`.

If a higher pity rule triggers during the ten-draw, that reward satisfies the ten-draw guarantee.

## Pity Rules

Pity progress is tracked per `group_id + user_id`.

Counters:

- `draws_since_mythic_plus`
- `draws_since_divine`
- `total_draws`

Rules:

- If the player has gone `50` draws without `mythic` or `divine`, the next draw is forced to `mythic`.
- If the player has gone `120` draws without `divine`, the next draw is forced to `divine`.
- Divine pity has priority over mythic pity.
- A natural or forced `mythic` resets `draws_since_mythic_plus`.
- A natural or forced `divine` resets both `draws_since_divine` and `draws_since_mythic_plus`.
- Lower-rarity draws increment both active pity counters.

The response should show remaining draws to both pity thresholds.

## Gear Pools

All gear rewards use existing item definitions and automatically roll affixes through the current loot system.

Rare pool:

- `moonsteel_sword`, `scarlet_moon_blade`, `silver_dragon_spear`, `ghost_lotus_dart`
- `cloudweave_armor`, `black_iron_plate`

Epic pool:

- `starforged_sword`, `thunder_soul_sword`
- `cloud_splitter_blade`, `thunderclap_blade`
- `tiger_roar_spear`, `meteor_halberd`
- `black_rain_needles`, `soul_lock_nails`
- `moonshadow_armor`, `phoenix_feather_armor`
- `dragon_scale_plate`, `thunder_plate`

Legendary pool:

- `sunfire_sword`, `dragon_spine_blade`, `sea_quelling_halberd`, `starfall_needles`
- `star_silk_armor`, `mountain_guard_plate`

Mythic pool:

- `void_cleaver_sword`, `emperor_jade_sword`
- `blood_sea_blade`, `heaven_cleaver_blade`
- `heaven_river_spear`, `world_pillar_halberd`
- `nether_blossom_dart`, `ten_thousand_venom_box`
- `mirage_armor`, `immortal_cloud_robe`
- `basalt_king_plate`, `demon_seal_plate`

Divine pool:

- `skyfall_sword`, `king_hell_blade`, `nine_suns_spear`, `silent_ending_needles`
- `galaxy_robe`, `heaven_fortress_plate`

If a configured item is missing, it should be skipped rather than crashing. Empty pools are a configuration error caught by tests.

## Data Model

Add a table for persistent pity state:

```sql
CREATE TABLE IF NOT EXISTS void_sacrifice_pity (
    group_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    total_draws INTEGER NOT NULL DEFAULT 0,
    draws_since_mythic_plus INTEGER NOT NULL DEFAULT 0,
    draws_since_divine INTEGER NOT NULL DEFAULT 0,
    updated_at INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (group_id, user_id)
);
```

This is intentionally separate from `players` so future lottery history or seasonal pools can evolve independently.

## Service Flow

1. Load the player by `group_id + user_id`.
2. Parse draw count as `1` or `10`.
3. Check required gold.
4. Load or create pity state.
5. Deduct gold.
6. Roll each draw in order.
7. Apply pity priority: divine pity, then mythic pity, then natural roll, then ten-draw guarantee if needed.
8. Grant consumables, gold refunds, and gear.
9. Update pity counters and player inventory.
10. Save player and pity state in one database transaction.
11. Return a structured result for formatting.

## Response Format

Single draw:

```text
「cxh」
🌌 虚空献祭 ×1
消耗金币:1000

1. 雷纹锁子甲[厚血(生命+14%)]  epic

🔮 距 mythic+ 保底:37抽
🌠 距 divine 保底:112抽
```

Ten draw:

```text
「cxh」
🌌 虚空献祭 ×10
消耗金币:10000

1. 金钟罩符 ×1
2. 雷纹锁子甲[厚血(生命+14%)]  epic
3. 返还金币 240
4. 虎骨酒 ×1
5. 月影轻甲[坚壁(防御+12%)]  epic
6. 金疮药 ×1
7. 续命丹 ×1
8. 凤羽宝衣[轻盈(防御+9% 生命+13%)]  epic
9. 返还金币 180
10. 血海长刀[锋锐(攻击+17%)]  mythic

🔮 距 mythic+ 保底:50抽
🌠 距 divine 保底:112抽
```

The ten-draw guarantee line appears only when the system actually upgraded a reward because the ten natural rolls had no `epic+`.

## Error Handling

Expected errors:

```text
你在当前世界还没有角色,先发「注册 角色名」吧~
用法:虚空献祭 [次数]，支持 1 或 10
金币不足(需 10000,当前 3719)
虚空献祭奖池配置异常,请稍后再试。
```

The bot should not expose stack traces to chat. Unexpected exceptions follow the existing generic bot error response.

## Testing

Core tests:

- Base rarity selection can return every configured tier under deterministic RNG.
- Ten-draw without natural `epic+` upgrades one reward to `epic`.
- Mythic pity triggers after 50 misses and resets after a `mythic+`.
- Divine pity triggers after 120 misses and resets both pity counters.
- Divine pity wins over mythic pity when both are due.
- Gear rewards receive affixes through the existing loot path.

Service tests:

- One draw deducts `1000` gold and persists reward plus pity state.
- Ten draws deduct `10000` gold and grants ten result entries.
- Insufficient gold deducts nothing and does not update pity.
- Pity state is scoped by `group_id + user_id`.

Bot tests:

- Standard commands and fuzzy aliases route to the sacrifice command.
- Formatter displays gear, consumables, refunds, guarantee text, and remaining pity counts.

## Non-Goals

- No paid currency or real-money purchase mechanics.
- No seasonal limited pool in this version.
- No auto-equip after drawing.
- No draw history command in this version.
