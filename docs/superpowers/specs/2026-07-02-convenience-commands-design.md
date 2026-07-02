# Convenience Commands Design

## Goal

Add player convenience commands for buying and equipping gear, refilling HP from backpack consumables, and using multiple consumables with automatic shop purchase fallback.

## Requirements

- `购买装备 <物品>` / `购买武器 <物品>` / `购买并装备 <物品>` buys one shop item and equips it immediately.
- Buy-and-equip rejects consumables before spending gold.
- `回满生命` / `回满血` uses existing backpack healing consumables until HP is full or healing items are exhausted. It does not auto-buy healing items.
- HP refill output lists each healing item name and quantity used.
- `使用` supports multiple consumables in one command, for example `使用 虎骨酒 蛮牛散 金疮药 *3`.
- For each requested consumable, if the item is missing from the backpack, the system attempts to buy one from the shop and then use it.
- Multi-use continues processing later items when one item fails, and returns per-item success/failure details.
- Stamina consumables used through multi-use still count toward the existing爆气 window.

## Architecture

- Extend `bot.command_parsing` with a multi-item parser that preserves existing single-item quantity syntax.
- Add service-layer functions in `app.services` for buy-and-equip, refill HP, and multi-use. Services own persistence and result summaries.
- Keep core item mutation in `game_core.loot` and shop purchase in `game_core.shop`.
- Update `bot.plugins.rpg` command handlers and `docs/game-commands.md`.

## Error Handling

- Missing arguments return usage messages.
- Buy-and-equip surfaces existing item, gold, and invalid slot errors.
- HP refill reports when HP is already full or no healing items are available.
- Multi-use records item-level failures instead of aborting the whole command, except when the character does not exist.
