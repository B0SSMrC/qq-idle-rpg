# Gear Affixes Design

## Goal

Add random weapon and armor affixes, allow players to reroll equipped gear for gold, and force combat events at depth 80 and deeper.

## Requirements

- Weapons use a weapon-only affix pool; armor uses an armor-only affix pool.
- Affixes can be positive, negative, or mixed.
- Positive effects can reach +20%; negative effects can reach -15%.
- Weapon pool includes lifesteal: each player attack restores a percentage of the damage dealt.
- New weapon/armor drops and shop purchases receive one affix automatically.
- Existing gear without affixes remains valid and gains an affix after reroll.
- Reroll command format: `重铸 武器`, `重铸 装备`, `重铸 武器 10`, `重铸 装备 10`.
- Reroll cost is 200 gold per attempt. Multiple rerolls keep the last result.
- From depth 80 onward every exploration step must be combat.

## Architecture

- Store affixes on `InventoryItem.affix` as JSON text, persisted in `inventory.affix`.
- Add `game_core.affixes` for affix pools, rolling, parsing, formatting, and stat helpers.
- Update `game_core.stats` and `game_core.combat` for percentage stats and lifesteal.
- Update `game_core.loot` and shop purchase paths so gear is non-stackable once affixes are involved.
- Add `app.services.do_reforge_equipped` and a `重铸` OneBot command.
- Update exploration event selection to force combat when `depth >= 80`.

## Affix Pools

Weapon affixes:

- `锋锐`: attack +8% to +20%.
- `嗜血`: lifesteal +5% to +15%.
- `破甲`: attack +5% to +12%.
- `钝刃`: attack -5% to -15%.
- `沉重`: defense -4% to -12%.
- `狂战`: attack +10% to +20%, defense -5% to -15%.
- `贪婪`: gold +10% to +20%, attack -5% to -12%.

Armor affixes:

- `坚壁`: defense +8% to +20%.
- `厚血`: HP +8% to +20%.
- `轻盈`: defense +5% to +12%, HP +5% to +12%.
- `破损`: defense -5% to -15%.
- `笨重`: attack -4% to -12%.
- `重装`: defense +10% to +20%, attack -5% to -15%.
- `血甲`: HP +10% to +20%, defense -5% to -12%.
