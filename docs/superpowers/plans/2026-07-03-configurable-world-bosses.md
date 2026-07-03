# Configurable World Bosses Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move world Boss definitions out of hardcoded constants into `data/world_bosses.yaml`, allowing the operator to add, remove, disable, and tune Bosses without code changes.

**Architecture:** Add a `WorldBossDef` config model and load it through the existing YAML config pipeline. Update world Boss repository helpers to create and query one active Boss per `group_id + boss_key`, while service and bot layers accept an optional Boss selector. Keep old commands compatible by defaulting to the first enabled Boss ordered by `tier`.

**Tech Stack:** Python 3.12, SQLite, PyYAML, NoneBot OneBot v11, pytest.

## Global Constraints

- Existing `进攻世界boss` must continue working and target the first enabled Boss.
- Operators can disable a Boss with `enabled: false`; disabled Bosses cannot spawn or be attacked.
- Existing world Boss history remains readable; no destructive migrations.
- Boss HP remains scaled by active player count using each Boss definition.
- All spend actions remain explicit enough to avoid accidental stamina loss.

---

### Task 1: Load Boss Config

**Files:**
- Create: `data/world_bosses.yaml`
- Modify: `game_core/models.py`
- Modify: `game_core/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `WorldBossDef`
- Produces: `GameConfig.world_bosses: dict[str, WorldBossDef]`

- [ ] Write failing config tests for loading enabled and disabled Boss definitions.
- [ ] Add `WorldBossDef` dataclass.
- [ ] Load and validate `data/world_bosses.yaml`.
- [ ] Verify `pytest tests/test_config.py -q`.
- [ ] Commit: `Add configurable world boss definitions`.

### Task 2: Support Multiple Configured Bosses in Repository

**Files:**
- Modify: `storage/world_boss_repo.py`
- Test: `tests/test_world_boss_db.py`

**Interfaces:**
- Consumes: `WorldBossDef`
- Produces: `create_or_get_active_boss(conn, group_id, boss_def, now, active_player_count)`
- Produces: `list_active_bosses(conn, group_id)`
- Produces: `get_active_boss(conn, group_id, boss_key=None)`

- [ ] Write failing tests for creating separate Boss rows per `boss_key`.
- [ ] Update create/get/retune/cooldown logic to use `WorldBossDef`.
- [ ] Keep legacy default constants for old tests only where harmless, but new paths use config.
- [ ] Verify `pytest tests/test_world_boss_db.py -q`.
- [ ] Commit: `Support configured world boss rows`.

### Task 3: Service Layer Boss Selection

**Files:**
- Modify: `app/services.py`
- Test: `tests/test_world_boss_services.py`

**Interfaces:**
- Produces: `WorldBossStatusResult.bosses`
- Produces: `do_world_boss_status(conn, cfg, group_id, now, boss_query="")`
- Produces: `do_attack_world_boss(conn, cfg, group_id, user_id, now, rng, boss_query="")`

- [ ] Write failing tests for status listing multiple Bosses and attacking Boss `2`.
- [ ] Add Boss selector parsing by tier, key, and name.
- [ ] Default old calls to first enabled Boss.
- [ ] Verify `pytest tests/test_world_boss_services.py -q`.
- [ ] Commit: `Add world boss selection services`.

### Task 4: Bot Commands, Formatting, and Docs

**Files:**
- Modify: `bot/formatting.py`
- Modify: `bot/fuzzy_commands.py`
- Modify: `bot/plugins/rpg.py`
- Modify: `docs/game-commands.md`
- Test: `tests/test_formatting.py`
- Test: `tests/test_fuzzy_commands.py`

**Interfaces:**
- Consumes: selected Boss service functions.
- Produces command forms: `世界boss`, `进攻世界boss 2`, `进攻世界boss Boss名`.

- [ ] Write failing formatting and fuzzy command tests.
- [ ] Render list status for all enabled Bosses.
- [ ] Pass parsed Boss selector from bot handlers into services.
- [ ] Document `data/world_bosses.yaml` operations.
- [ ] Verify formatting/fuzzy/architecture tests.
- [ ] Commit: `Add configurable world boss commands`.

### Task 5: Final Verification

**Files:**
- Test-only verification.

- [ ] Run `pytest -q`.
- [ ] Run a small manual smoke script for default Boss and Boss `2`.
- [ ] Inspect `git status --short --branch`.
