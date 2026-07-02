# Fuzzy Command Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic fuzzy command routing for all existing OneBot RPG commands.

**Architecture:** A pure parser in `bot/fuzzy_commands.py` maps raw text to a normalized command id and argument string. `bot/plugins/rpg.py` keeps exact `on_command` handlers and adds a fuzzy fallback that reuses the same service logic.

**Tech Stack:** Python 3.10+, standard library `re` and `difflib`, NoneBot OneBot plugin, pytest.

## Global Constraints

- Do not add an LLM call for command parsing.
- Do not add third-party dependencies.
- Do not fuzzy-match item names or character names.
- Keep `buy`, `buy_equip`, `sell_gear`, and `refill_stamina` conservative.
- Low-confidence inputs must fall through to unknown-command replies.
- Preserve existing OneBot exact command behavior.

---

### Task 1: Pure Fuzzy Parser

**Files:**
- Create: `bot/fuzzy_commands.py`
- Create: `tests/test_fuzzy_commands.py`

**Interfaces:**
- Produces: `ParsedCommand(command: str, arg: str, confidence: float, matched_alias: str)`
- Produces: `parse_fuzzy_command(raw: str) -> ParsedCommand | None`

- [ ] **Step 1: Write failing parser tests**

Cover all command ids, compact forms, natural read-only phrases, and safety-sensitive cases:

```python
def test_parse_reforge_compact_count():
    parsed = parse_fuzzy_command("重铸武器10")
    assert parsed.command == "reforge"
    assert parsed.arg == "武器 10"
```

- [ ] **Step 2: Run parser tests**

Run: `python -m pytest tests/test_fuzzy_commands.py -q`

Expected: failures because `bot.fuzzy_commands` does not exist.

- [ ] **Step 3: Implement parser**

Use deterministic matching tables and helper functions. Keep destructive and gold-spending commands explicit.

- [ ] **Step 4: Run parser tests**

Run: `python -m pytest tests/test_fuzzy_commands.py -q`

Expected: all parser tests pass.

### Task 2: OneBot Fuzzy Fallback

**Files:**
- Modify: `bot/plugins/rpg.py`
- Test: existing command and service tests

**Interfaces:**
- Consumes: `parse_fuzzy_command(raw)`.
- Reuses existing service functions and response renderers.

- [ ] **Step 1: Add internal handler helpers**

Refactor command handlers that need arguments into helpers accepting `arg: str`, such as `_handle_buy_args`, `_handle_reforge_args`, and `_handle_travel_explore_args`.

- [ ] **Step 2: Add fuzzy `on_message` fallback**

Place it before unknown-command fallback and after exact `on_command` handlers. If `parse_fuzzy_command` returns `None`, do nothing and let unknown-command reply.

- [ ] **Step 3: Dispatch normalized command ids**

Call the same helper logic used by exact command handlers. No game rule duplication.

- [ ] **Step 4: Run targeted tests**

Run: `python -m pytest tests/test_command_parsing.py tests/test_fuzzy_commands.py -q`

Expected: all selected tests pass.

### Task 3: Documentation and Full Verification

**Files:**
- Modify: `docs/game-commands.md`

- [ ] **Step 1: Document fuzzy command usage**

Add examples for compact and natural command forms.

- [ ] **Step 2: Run full verification**

Run:

```bash
python -m pytest -q
python -m compileall -q bot app game_core storage
```

Expected: full suite passes and compileall exits 0.
