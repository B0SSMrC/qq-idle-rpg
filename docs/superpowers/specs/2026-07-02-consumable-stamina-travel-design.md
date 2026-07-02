# Consumable, Stamina Refill, and Travel Explore Design

## Goal

Add three player convenience features to the OneBot RPG: batch consumable use, one-command stamina refill with overuse penalty, and travel-to-depth plus immediate exploration.

## Requirements

- Batch consumable use accepts `使用 物品 数量`, `使用 物品 *数量`, and compact command forms such as `使用物品 数量`.
- Batch use applies only to consumables. Healing and stamina consumables apply repeatedly up to the requested count. Attack and defense consumables may be requested in batches, but their buff value is still replacement-style rather than stacking.
- `回满体力` buys the amount of `回气丹` needed to refill the player's stamina to max. It does not consume inventory. Cost equals `ceil(missing_stamina / 回气丹回复量) * 回气丹价格`.
- Every 5 minutes, stamina restored by回气丹-like direct refill is tracked against a hidden 300-stamina soft cap. Crossing the cap applies `爆气`: attack -15% and defense -20% for 10 minutes, and the bot tells the player that爆气 was triggered.
- The hidden cap value is not displayed to players.
- `回到 层数 并探索` first validates and moves to an already reached depth, then immediately performs normal exploration from that depth.

## Architecture

- Keep command parsing in `bot/plugins/rpg.py`, matching existing command handlers.
- Put game rules in `app/services.py` and `game_core/loot.py` so tests can exercise them without OneBot.
- Extend persisted player state with a refill window and a timed negative buff. Timed negative buff affects `game_core/stats.py`, while existing step buffs continue to behave as before.
- Add Markdown command documentation updates after behavior changes.

## Error Handling

- Invalid or missing quantities return friendly usage errors.
- Non-consumable batch use keeps the existing `不是消耗品` error.
- Insufficient gold for `回满体力` returns a clear required/current gold message.
- `回到 层数 并探索` reuses existing depth validation errors.
