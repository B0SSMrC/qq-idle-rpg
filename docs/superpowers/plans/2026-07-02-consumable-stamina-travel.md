# Consumable Stamina Travel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement batch consumable use, one-command stamina refill with爆气 penalty, and travel-to-depth plus immediate exploration.

**Architecture:** Command handlers parse player text and delegate to services. Services coordinate persistence, while game_core modules hold deterministic game rules. Player persistence gains minimal extra columns for refill-window tracking and timed爆气 state.

**Tech Stack:** Python 3.12, NoneBot2 OneBot v11, SQLite, pytest.

## Global Constraints

- Use TDD: write failing tests before production code.
- Preserve current OneBot-only architecture.
- Do not display the hidden 300 stamina soft cap.
- Keep existing step-based positive buff behavior unchanged.

---

### Task 1: Batch Consumable Use

**Files:**
- Modify: `game_core/loot.py`
- Modify: `app/services.py`
- Modify: `bot/plugins/rpg.py`
- Test: `tests/test_loot.py`
- Test: `tests/test_services_actions.py`

**Interfaces:**
- Produces: `use_item(player: Player, item_id: str, cfg: GameConfig, quantity: int = 1) -> int`
- Produces: `do_use(conn, cfg, group_id, user_id, item_query, quantity=1) -> Player`

- [ ] Write failing tests for using 3 HP potions, rejecting quantity 0, and service persistence.
- [ ] Run targeted tests and confirm they fail because quantity support is missing.
- [ ] Add quantity support to loot and services.
- [ ] Update command parsing for `使用 物品 3`, `使用 物品 *3`, and `使用物品 3`.
- [ ] Run targeted tests and then the full suite.

### Task 2: Full Stamina Refill and 爆气

**Files:**
- Modify: `game_core/models.py`
- Modify: `storage/db.py`
- Modify: `storage/repository.py`
- Modify: `game_core/stats.py`
- Modify: `app/services.py`
- Modify: `bot/formatting.py`
- Modify: `bot/plugins/rpg.py`
- Test: `tests/test_db.py`
- Test: `tests/test_repository.py`
- Test: `tests/test_stats.py`
- Test: `tests/test_services_actions.py`

**Interfaces:**
- Produces: `Player.stamina_refill_window_start`, `Player.stamina_refill_window_amount`, `Player.overdrive_until`
- Produces: `do_refill_stamina(conn, cfg, group_id, user_id, now) -> tuple[Player, int, bool]`

- [ ] Write failing tests for exact refill cost, insufficient gold, threshold-triggered爆气, DB migration, repository roundtrip, and stats penalty.
- [ ] Run targeted tests and confirm they fail for missing fields/functions.
- [ ] Add DB columns with migration-safe `ALTER TABLE`.
- [ ] Persist new player fields.
- [ ] Implement refill service using 回气丹 config.
- [ ] Apply timed attack/defense penalty when `now < overdrive_until`.
- [ ] Add command handler and reply formatting.
- [ ] Run targeted tests and then the full suite.

### Task 3: Travel and Explore Combo

**Files:**
- Modify: `app/services.py`
- Modify: `bot/plugins/rpg.py`
- Test: `tests/test_services_actions.py`

**Interfaces:**
- Produces: `do_travel_and_explore(conn, cfg, group_id, user_id, depth_query, now, rng) -> tuple[Player, ExploreResult]`

- [ ] Write failing test that moves to depth 35 and then explores from depth 35.
- [ ] Run targeted test and confirm it fails because combo service is missing.
- [ ] Implement combo service by reusing travel validation and exploration.
- [ ] Add `回到` command handler with `并探索` parsing.
- [ ] Run targeted tests and then the full suite.

### Task 4: Documentation

**Files:**
- Modify: `docs/game-commands.md`

**Interfaces:**
- Consumes implemented command behavior.

- [ ] Add batch use, 回满体力, and 回到并探索 to the command document.
- [ ] Verify doc examples match command handlers.
