# Fuzzy Command Routing Design

## Goal

Players can send natural or slightly imprecise QQ messages and still trigger the correct RPG command without relying on LLM inference or exact command text.

## Scope

- Add a local deterministic parser for command intent only.
- Keep item names, character names, depth values, and quantities as user-provided arguments.
- Preserve existing exact `on_command` handlers.
- Add a fuzzy `on_message` fallback for messages that exact handlers do not catch.
- Keep unknown-command replies for low-confidence or unsupported messages.

## Command Coverage

The parser standardizes these command ids:

- `register`
- `explore`
- `status`
- `inventory`
- `equip`
- `buy_equip`
- `unequip`
- `use`
- `refill_hp`
- `refill_stamina`
- `reforge`
- `shop`
- `buy`
- `sell_gear`
- `travel`
- `travel_explore`
- `ranking`
- `help`

## Matching Rules

1. Exact command words and aliases match first.
2. Compact forms without spaces are supported, such as `重铸武器10`, `购买装备铁剑`, and `回到35并探索`.
3. Natural trigger phrases are supported for common read-only commands, such as `查看背包`, `看看状态`, `打开商店`, and `帮助菜单`.
4. Light typo matching may use `difflib`, but only against command words, not arguments.
5. Low-confidence matches return `None` so the existing unknown-command pool replies.

## Safety Rules

- `出售装备` is destructive and must not trigger from generic messages that merely contain `装备`.
- `购买` and `购买装备` must stay distinct.
- `回满体力` costs gold and must not trigger from generic stamina chat.
- The parser must not auto-correct item names.
- Fuzzy routing must reuse existing service logic and locks instead of duplicating game behavior.

## Expected Examples

- `重铸武器` -> `reforge`, arg `武器`
- `重铸武器10` -> `reforge`, arg `武器 10`
- `查看背包` -> `inventory`, empty arg
- `看看状态` -> `status`, empty arg
- `打开商店` -> `shop`, empty arg
- `买铁剑` -> `buy`, arg `铁剑`
- `买装备铁剑` -> `buy_equip`, arg `铁剑`
- `使用金疮药3` -> `use`, arg `金疮药3`
- `回到35并探索` -> `travel_explore`, arg `35 并探索`
- `去35层` -> `travel`, arg `35`
- `排行榜深度` -> `ranking`, arg `深度`

## Testing

- Unit-test the parser with all command ids.
- Unit-test ambiguous and safety-sensitive inputs.
- Run the full project test suite after wiring the parser into the bot plugin.
