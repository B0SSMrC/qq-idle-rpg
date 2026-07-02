# World Boss Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a group-scoped world Boss event where players attack a shared Boss, atomically update HP and damage contribution, and receive contribution-based rewards when the Boss is defeated.

**Architecture:** Store world Boss state in SQLite tables keyed by `group_id`; implement core logic in focused `game_core/world_boss.py` and persistence helpers in `storage/world_boss_repo.py`; expose service functions through `app/services.py` and OneBot commands in `bot/plugins/rpg.py`. Background announcements run from the bot process and read committed database state only.

**Tech Stack:** Python 3.10+, sqlite3, pytest, NoneBot OneBot, existing game config/stats/loot/affix systems.

## Global Constraints

- Each `group_id` has at most one active world Boss.
- Players join by sending `进攻世界boss`.
- Each attack costs `50` stamina.
- A single attack continues until the player dies or the Boss is defeated.
- If the player loses, they return immediately, lose `5%` current gold, and recover to full HP.
- Rewards are calculated by each player's percentage of total effective damage.
- Boss is defeated, then the group enters a `6 hours` cooldown before the next Boss spawns.
- Boss exists while alive and announces Boss HP and player damage contribution every `10 minutes`.
- Every world Boss attack settlement must update Boss HP atomically inside one database transaction.
- Announcement reads only committed database state and must never compute HP from memory cache.
- World Boss rare gear chance must be higher than exploration drop chance, and higher damage percentage must increase the chance.

---

### Task 1: Database Tables And Repository

**Files:**
- Modify: `storage/db.py`
- Create: `storage/world_boss_repo.py`
- Test: `tests/test_world_boss_db.py`

**Interfaces:**
- Produces: `create_or_get_active_boss(conn, group_id, now, active_player_count) -> sqlite3.Row`
- Produces: `get_active_boss(conn, group_id) -> sqlite3.Row | None`
- Produces: `list_due_announcements(conn, now) -> list[sqlite3.Row]`
- Produces: `mark_announced(conn, boss_id, now) -> None`

- [ ] **Step 1: Write failing DB migration tests**

```python
def test_init_db_creates_world_boss_tables():
    conn = db.get_conn(":memory:")
    db.init_db(conn)
    tables = {
        r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert {"world_bosses", "world_boss_damage", "world_boss_rewards"} <= tables
```

- [ ] **Step 2: Run DB test**

Run: `python -m pytest tests/test_world_boss_db.py -q`

Expected: fail because tables/repository do not exist yet.

- [ ] **Step 3: Implement schema and repository**

Add `world_bosses`, `world_boss_damage`, and `world_boss_rewards` to `storage/db.py`. Implement repository helpers in `storage/world_boss_repo.py`.

- [ ] **Step 4: Run DB test**

Run: `python -m pytest tests/test_world_boss_db.py -q`

Expected: pass.

### Task 2: Core World Boss Battle And Rewards

**Files:**
- Create: `game_core/world_boss.py`
- Test: `tests/test_world_boss_core.py`

**Interfaces:**
- Produces: `WORLD_BOSS_STAMINA_COST = 50`
- Produces: `WORLD_BOSS_GOLD_LOSS_PCT = 0.05`
- Produces: `simulate_world_boss_attack(player, boss, cfg, rng) -> WorldBossAttackSimulation`
- Produces: `roll_world_boss_rewards(damage_percent, player_level, active_player_count, cfg, rng) -> WorldBossReward`

- [ ] **Step 1: Write failing core tests**

Cover stamina constants, battle simulation returning damage, gold loss percent, and reward rare drop chance increasing with damage percent.

- [ ] **Step 2: Run core tests**

Run: `python -m pytest tests/test_world_boss_core.py -q`

Expected: fail because module does not exist.

- [ ] **Step 3: Implement core module**

Implement Boss stat defaults, combat loop, and deterministic reward calculation using existing item definitions and `loot.add_item` later in services.

- [ ] **Step 4: Run core tests**

Run: `python -m pytest tests/test_world_boss_core.py -q`

Expected: pass.

### Task 3: Atomic Attack Settlement Service

**Files:**
- Modify: `app/services.py`
- Modify: `storage/world_boss_repo.py`
- Test: `tests/test_world_boss_services.py`

**Interfaces:**
- Produces: `do_world_boss_status(conn, cfg, group_id, now) -> WorldBossStatusResult`
- Produces: `do_attack_world_boss(conn, cfg, group_id, user_id, now, rng) -> WorldBossAttackResult`
- Produces: `get_world_boss_ranking(conn, cfg, group_id, now) -> WorldBossStatusResult`

- [ ] **Step 1: Write failing service tests**

Cover spawning a Boss, attack consuming 50 stamina, losing player losing 5% gold and healing to max HP, damage contribution accumulation, Boss HP reduced by effective damage, and version conflict retry.

- [ ] **Step 2: Run service tests**

Run: `python -m pytest tests/test_world_boss_services.py -q`

Expected: fail because service functions do not exist.

- [ ] **Step 3: Implement service functions**

Use one SQLite transaction for each attack settlement. Use optimistic locking with `version`; if update affects 0 rows, rollback, reload, recalculate effective damage from theoretical damage, and retry up to 3 times.

- [ ] **Step 4: Run service tests**

Run: `python -m pytest tests/test_world_boss_services.py -q`

Expected: pass.

### Task 4: Formatting And Bot Commands

**Files:**
- Modify: `bot/formatting.py`
- Modify: `bot/fuzzy_commands.py`
- Modify: `bot/plugins/rpg.py`
- Test: `tests/test_fuzzy_commands.py`

**Interfaces:**
- Produces: `render_world_boss_status(result) -> str`
- Produces: `render_world_boss_attack(result) -> str`
- Adds commands: `世界boss`, `世界boss状态`, `世界boss排行`, `进攻世界boss`, `攻击世界boss`, `挑战世界boss`

- [ ] **Step 1: Write failing command parser tests**

Add fuzzy parser coverage for `世界boss`, `boss排行`, `进攻boss`, `打世界boss`.

- [ ] **Step 2: Run parser tests**

Run: `python -m pytest tests/test_fuzzy_commands.py -q`

Expected: fail until parser is extended.

- [ ] **Step 3: Implement formatting and bot handlers**

Wire commands to service functions. Reuse `_guard`, `_scope`, and group/player locks as appropriate; service transaction remains the source of correctness.

- [ ] **Step 4: Run parser and formatting tests**

Run: `python -m pytest tests/test_fuzzy_commands.py tests/test_formatting.py -q`

Expected: pass.

### Task 5: Ten-Minute Announcement Job

**Files:**
- Modify: `bot/state.py`
- Modify: `bot/plugins/rpg.py`
- Test: `tests/test_world_boss_services.py`

**Interfaces:**
- Produces: `services.get_due_world_boss_announcements(conn, cfg, now) -> list[WorldBossStatusResult]`
- Produces: `services.mark_world_boss_announced(conn, boss_id, now) -> None`

- [ ] **Step 1: Write failing announcement tests**

Cover due announcements every 10 minutes and skip Bosses updated in the last 3 seconds.

- [ ] **Step 2: Run announcement tests**

Run: `python -m pytest tests/test_world_boss_services.py -q`

Expected: fail until announcement service exists.

- [ ] **Step 3: Implement announcement scan**

Use an `asyncio` background loop started by NoneBot startup. Every 60 seconds, read committed Boss state, send group announcements, then mark announced.

- [ ] **Step 4: Run announcement tests**

Run: `python -m pytest tests/test_world_boss_services.py -q`

Expected: pass.

### Task 6: Documentation And Full Verification

**Files:**
- Modify: `docs/game-commands.md`

- [ ] **Step 1: Document world Boss commands**

Add supported commands, attack cost, defeat penalty, reward contribution, refresh cooldown, and 10-minute announcements.

- [ ] **Step 2: Run full verification**

Run:

```bash
python -m pytest -q
python -m compileall -q bot app game_core storage
```

Expected: full suite passes and compileall exits 0.
