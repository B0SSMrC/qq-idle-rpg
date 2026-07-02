# World Boss Design

## Goal

Add a group-wide world Boss event where players in the same QQ group fight a shared Boss, contribute damage together, and receive rewards based on damage contribution after the Boss is defeated.

## Core Rules

- Each `group_id` has at most one active world Boss.
- Players join by sending `进攻世界boss`.
- Each attack costs `50` stamina.
- A single attack continues until the player dies or the Boss is defeated.
- If the player loses, they return immediately, lose `5%` current gold, and recover to full HP.
- Boss HP is the highest HP among all monsters and is shared by all players in the group.
- Boss rewards are settled when the Boss is defeated.
- Rewards are calculated by each player's percentage of total effective damage.

## Suggested Commands

- `世界boss`: show current Boss status.
- `世界boss状态`: same as `世界boss`.
- `进攻世界boss`: consume stamina and attack the active Boss.
- `攻击世界boss`: alias of `进攻世界boss`.
- `挑战世界boss`: alias of `进攻世界boss`.
- `世界boss排行`: show current damage ranking.

The fuzzy command parser can later support compact and natural forms such as `打世界boss`, `进攻boss`, and `boss排行`, but implementation should keep spend actions explicit enough to avoid accidental stamina loss.

## Boss Lifecycle

- When no active Boss exists and cooldown has expired, the system spawns a new Boss for that group.
- When a Boss is defeated, it enters a cooldown period before the next Boss spawns.
- Recommended cooldown: `6 hours` after defeat.
- Recommended maximum active duration: `48 hours`; if the Boss is not defeated by then, it escapes and the group enters the same cooldown.
- The Boss exists per group, not globally across all groups.

## Boss Stats

The current deepest normal monster is around `2200 HP`, so the world Boss should start far above that.

Recommended base formula:

```text
boss_hp_max = 120000 + active_player_count * 30000
```

Where `active_player_count` means players in the group who explored or attacked a world Boss in the last `7 days`.

Suggested first Boss:

```yaml
id: world_boss_abyss_emperor
name: 万劫魔君
atk: 360
def: 180
hp: dynamic
```

The Boss should be strong enough that one player cannot casually defeat it, but not so strong that a small group cannot make visible progress.

## Attack Flow

1. Player sends `进攻世界boss`.
2. System checks player exists.
3. System checks the current group has an alive Boss.
4. System checks player stamina is at least `50`.
5. System starts a database transaction.
6. System deducts `50` stamina.
7. System simulates the attack until player death or Boss death.
8. System computes `effective_damage = min(theoretical_damage, boss.hp_current)`.
9. System atomically updates Boss HP, damage contribution, player state, and gold loss in the same transaction.
10. System commits the transaction.
11. System replies with the attack result.
12. If the Boss was defeated, system sends the defeat announcement and reward results.

## Required Concurrency Rule

Every world Boss attack settlement must update Boss HP atomically inside one database transaction.

The transaction must include:

- Boss HP update.
- Boss status update.
- Boss version update.
- Player stamina deduction.
- Player HP recovery if defeated.
- Player gold loss if defeated.
- Player damage contribution update.
- Reward-settlement marker if this attack defeats the Boss.

The implementation should use optimistic locking with a `version` column.

Recommended update pattern:

```sql
UPDATE world_bosses
SET hp_current = MAX(0, hp_current - :effective_damage),
    status = CASE
      WHEN hp_current - :effective_damage <= 0 THEN 'dead'
      ELSE 'alive'
    END,
    version = version + 1,
    updated_at = :now
WHERE id = :boss_id
  AND status = 'alive'
  AND version = :old_version;
```

If the update affects `0` rows, another player updated the Boss first. The system should roll back, reload the latest Boss state, keep the player's already simulated theoretical damage, recalculate `effective_damage`, and retry the transaction up to `3` times.

If the Boss is already dead after reload, the attack should not duplicate rewards. It can either return no effective damage or apply only the valid damage before death if the earlier transaction recorded it.

Only the transaction that changes Boss status from `alive` to `dead` may create the defeat settlement.

## Announcement Rules

- While a Boss is alive, the bot announces Boss HP and player damage contribution every `10 minutes`.
- Announcement reads only committed database state.
- Announcement must never compute HP from memory cache.
- If a Boss was updated very recently, for example within `3 seconds`, the announcement job may delay a few seconds and reread to avoid posting mid-burst stale-looking status.

Recommended announcement:

```text
🌑 世界Boss: 万劫魔君
❤️ HP 86320/210000 (41.1%)
⚔️ 参战人数: 4
🏆 伤害贡献
1. cxh  52340伤害  42.1%
2. Crazy  38800伤害  31.2%
3. zx  14200伤害  11.4%

发送「进攻世界boss」加入战斗。
```

## Rewards

Rewards are granted after Boss defeat based on each player's damage percentage.

Players must deal at least `1%` total Boss damage to enter the full reward pool. Players below `1%` receive only a small participation gold reward.

Recommended reward parts:

1. Participation reward:

```text
gold = 800 + player_level * 30
consumables = random 1-3 from 金疮药, 续命丹, 九转还魂丹, 虎骨酒, 金钟罩符
```

2. Damage-share gold:

```text
boss_gold_pool = 20000 + active_player_count * 5000
player_bonus_gold = boss_gold_pool * damage_percent
```

3. Gear drop:

```text
normal_gear_chance = 20% + damage_percent * 80%
rare_gear_chance = 8% + damage_percent * 60%
mythic_or_high_tier_chance = 2% + damage_percent * 20%
```

World Boss rare gear chance must be higher than exploration drop chance, and higher damage percentage must increase the chance.

Suggested drop pool should focus on level 70-100 equipment:

- Mid-high pool: 雷魂剑, 裂云刀, 流星画戟, 锁魂钉, 雷纹锁子甲, 凤羽宝衣.
- High-contribution pool: 虚空断岳剑, 血海长刀, 天河龙枪, 冥花飞刃, 蜃楼幻甲, 玄武王铠.
- Very rare pool: 天坠归墟剑, 阎罗断罪刀, 九曜焚天枪, 无声断命针, 星河万象衣, 天门不破铠.

Gear rewards should use the existing affix system, so dropped weapons and armor roll affixes automatically.

## Suggested Database Tables

`world_bosses`:

- `id`
- `group_id`
- `boss_key`
- `name`
- `hp_max`
- `hp_current`
- `atk`
- `def`
- `status`: `alive`, `dead`, `escaped`, `cooldown`
- `version`
- `spawned_at`
- `expires_at`
- `next_spawn_at`
- `last_announcement_at`
- `updated_at`

`world_boss_damage`:

- `boss_id`
- `group_id`
- `user_id`
- `player_name`
- `damage`
- `attack_count`
- `updated_at`

`world_boss_rewards`:

- `boss_id`
- `group_id`
- `user_id`
- `damage`
- `damage_percent`
- `gold`
- `items_json`
- `claimed_at`

The reward table can prevent duplicate settlement if a process restarts during defeat handling.

## Example Attack Result

```text
「cxh」
⚔️ 你向世界Boss发起进攻,鏖战37回合后倒下。
本次造成 12840 伤害。
💰 损失金币 5%: -420
❤️ 已回满生命。
⚡ 消耗体力 50
Boss剩余 HP: 86320/210000
```

## Example Defeat Result

```text
🌑 世界Boss 万劫魔君 已被击败!

🏆 伤害排行
1. cxh  52340伤害  42.1%
2. Crazy  38800伤害  31.2%
3. zx  14200伤害  11.4%

「cxh」
造成 42.1% 伤害
获得: 17640金币、九转还魂丹×2、虎骨酒×1
✨ 掉落: 血海长刀[锋锐(攻击+18%)]
```

## Implementation Notes

- Use existing `group_id` as the world scope.
- Reuse existing player stats, combat math, item grant, and affix rolling where possible.
- Add world Boss combat as a separate service module rather than mixing it into dungeon exploration.
- Announcement should be a background task in the OneBot process.
- If adding a scheduler dependency is acceptable, use `nonebot-plugin-apscheduler`; otherwise use an `asyncio` loop started during bot startup.
