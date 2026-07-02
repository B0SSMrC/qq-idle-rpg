# Gear Affixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add gear affixes, rerolling, lifesteal, and depth-80 forced combat.

**Architecture:** Affix definitions and helpers live in `game_core.affixes`; inventory rows persist an `affix` JSON string; existing stat and combat services consume affix helpers. Reroll orchestration stays in `app.services`, and OneBot only parses command text and formats the result.

**Tech Stack:** Python 3.12, SQLite, NoneBot2 OneBot v11, pytest.

## Global Constraints

- Use TDD: write failing tests before production code.
- Existing saves without affixes must remain readable.
- Depth 80+ exploration must never produce treasure-only progress.
- Reroll cost is exactly 200 gold per attempt.

---

### Task 1: Affix Model And Persistence

**Files:**
- Create: `game_core/affixes.py`
- Modify: `game_core/models.py`
- Modify: `storage/db.py`
- Modify: `storage/repository.py`
- Test: `tests/test_affixes.py`
- Test: `tests/test_repository.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Produces: `roll_affix(slot: str, rng) -> str`
- Produces: `format_affix(affix: str) -> str`
- Produces: `InventoryItem.affix: str`

### Task 2: Affix Stats And Lifesteal

**Files:**
- Modify: `game_core/stats.py`
- Modify: `game_core/combat.py`
- Modify: `game_core/exploration.py`
- Test: `tests/test_stats.py`
- Test: `tests/test_combat.py`
- Test: `tests/test_exploration.py`

**Interfaces:**
- Produces: `lifesteal(player, cfg) -> float`
- Produces: `gold_bonus(player, cfg) -> float`

### Task 3: Gear Generation And Reroll

**Files:**
- Modify: `game_core/loot.py`
- Modify: `game_core/shop.py`
- Modify: `app/services.py`
- Modify: `bot/plugins/rpg.py`
- Test: `tests/test_loot.py`
- Test: `tests/test_shop.py`
- Test: `tests/test_services_actions.py`

**Interfaces:**
- Produces: `do_reforge_equipped(conn, cfg, group_id, user_id, slot_query, times, rng)`

### Task 4: Formatting And Documentation

**Files:**
- Modify: `bot/formatting.py`
- Modify: `docs/game-commands.md`
- Test: `tests/test_formatting.py`

**Interfaces:**
- Consumes affix format helpers.
