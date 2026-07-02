# Convenience Commands Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement buy-and-equip, HP refill, and multi-consumable use commands.

**Architecture:** Parsing stays in `bot.command_parsing`; durable game mutations stay in `app.services`; low-level inventory behavior stays in `game_core.loot` and `game_core.shop`. Tests cover parser behavior and service behavior before command wiring.

**Tech Stack:** Python 3.12, NoneBot2 OneBot v11, SQLite, pytest.

## Global Constraints

- Use TDD: write failing tests before production code.
- Preserve current OneBot-only architecture.
- Do not auto-buy healing items for `回满生命`.
- Continue item-level processing for multi-use failures.

---

### Task 1: Command Parsing

**Files:**
- Modify: `bot/command_parsing.py`
- Test: `tests/test_command_parsing.py`

**Interfaces:**
- Produces: `parse_multi_item_quantities(raw: str) -> list[tuple[str, int]]`

- [ ] Write failing tests for `虎骨酒 蛮牛散` and `金疮药 *3 虎骨酒`.
- [ ] Run parser tests and confirm failure.
- [ ] Implement parser by tokenizing whitespace and attaching `*数量`/`数量` tokens to the previous item.
- [ ] Run parser tests and confirm pass.

### Task 2: Service Behaviors

**Files:**
- Modify: `app/services.py`
- Test: `tests/test_services_actions.py`

**Interfaces:**
- Produces: `do_buy_and_equip(conn, cfg, group_id, user_id, item_query)`
- Produces: `do_refill_hp(conn, cfg, group_id, user_id)`
- Produces: `do_use_many(conn, cfg, group_id, user_id, requests, now=None)`

- [ ] Write failing tests for buy-and-equip, rejecting consumables, HP refill item summary, insufficient healing, multi-use auto-buy, and per-item failure continuation.
- [ ] Run targeted tests and confirm failure.
- [ ] Implement minimal result dataclasses and service functions.
- [ ] Run targeted tests and confirm pass.

### Task 3: Bot Commands And Docs

**Files:**
- Modify: `bot/plugins/rpg.py`
- Modify: `docs/game-commands.md`
- Test: existing full suite

**Interfaces:**
- Consumes service functions from Task 2.

- [ ] Add `购买装备`/`购买武器`/`购买并装备` handler.
- [ ] Add `回满生命`/`回满血` handler.
- [ ] Update `使用` handler to call multi-use when multiple item requests are present.
- [ ] Update help text and command documentation.
- [ ] Run full test suite and compile check.
