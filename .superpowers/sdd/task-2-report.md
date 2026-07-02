# Task 2 Report: Materials and Core Equipment Progression

## Implementation summary

- Added four material item definitions to `data/items.yaml`:
  - `refined_iron`
  - `black_iron`
  - `star_meteorite`
  - `divine_forge_crystal`
- Created `game_core/equipment_progression.py` with the pure core progression interfaces required by the brief:
  - `MATERIAL_ITEM_IDS`
  - `gear_growth_stats(inv, item)`
  - `dismantle_unequipped_gear(player, cfg, slot_filter="all")`
  - `enhance_equipped(player, cfg, slot, times=1)`
  - `star_up_equipped(player, cfg, slot)`
- Added focused tests in `tests/test_equipment_progression.py`.
- Preserved inventory behavior by:
  - keeping equipped gear untouched during dismantle
  - keeping unrelated inventory entries untouched
  - granting dismantle materials only after the kept inventory is finalized
  - consuming duplicate gear atomically for star-up fallback decisions

## RED / GREEN TDD evidence

### RED

1. Added `tests/test_equipment_progression.py` before creating any production code.
2. Ran:

```bash
pytest tests/test_equipment_progression.py -q
```

3. Observed expected failure:
   - `ModuleNotFoundError: No module named 'game_core.equipment_progression'`

### GREEN

1. Implemented the minimum scoped production changes in:
   - `data/items.yaml`
   - `game_core/equipment_progression.py`
2. Re-ran:

```bash
pytest tests/test_equipment_progression.py -q
```

3. Result:
   - `8 passed`

## Tests run with results

1. `pytest tests/test_equipment_progression.py -q`
   - Result: `8 passed`
2. `pytest tests/test_config.py tests/test_equipment_progression.py -q`
   - Result: `19 passed`

## Files changed

- `D:\Claude Code\qq-idle-rpg\data\items.yaml`
- `D:\Claude Code\qq-idle-rpg\game_core\equipment_progression.py`
- `D:\Claude Code\qq-idle-rpg\tests\test_equipment_progression.py`

## Self-review

- Scope stayed within the task-owned files only.
- The implementation matches the brief’s public interfaces and constants.
- Dismantle logic avoids the common rebuild bug where newly granted materials can be duplicated or unrelated consumables can be lost.
- Material consumption validates availability before removal.
- Duplicate-item star-up only removes duplicates when enough exist, avoiding partial consumption.
- Focused tests cover config presence, dismantle behavior, enhance behavior, multi-enhance stopping, stat growth, duplicate-first star-up, material fallback star-up, and missing equipped-slot rejection.

## Concerns

- No additional integration tests were added outside the briefed scope, so service-layer wiring and presentation behavior remain intentionally unverified in this task.

## Review-fix addendum

### RED

Added two focused regression tests in `tests/test_equipment_progression.py`:

- `test_enhance_rejects_unsupported_slots`
- `test_star_up_rejects_unsupported_slots`

Ran:

```bash
pytest tests/test_equipment_progression.py -q -k unsupported_slots
```

Observed failure before the fix:

- `Failed: DID NOT RAISE GameError`
- Both tests failed because accessory slots were still accepted by the core API.

### GREEN

Updated `game_core/equipment_progression.py` to reject any slot not in `{"weapon", "armor"}` before looking up equipped gear.

Re-ran:

```bash
pytest tests/test_equipment_progression.py -q -k unsupported_slots
pytest tests/test_equipment_progression.py -q
```

Result:

- `2 passed, 8 deselected`
- `10 passed`

## Review-fix addendum 2

### RED

Added a focused regression test in `tests/test_equipment_progression.py`:

- `test_dismantle_rejects_unsupported_slot_filter`

Ran:

```bash
pytest tests/test_equipment_progression.py -q
```

Observed failure before the fix:

- `Failed: DID NOT RAISE GameError`
- `dismantle_unequipped_gear(p, CFG, "accessory")` silently no-op'd instead of rejecting the unsupported filter

### GREEN

Updated `game_core/equipment_progression.py` to validate `slot_filter` before iterating inventory:

- accepts exactly `all`, `weapon`, and `armor`
- raises `GameError` for anything else

Also cleaned up `tests/test_equipment_progression.py` so unsupported-slot tests use a local deep-copied config instead of mutating module-global `CFG.items`.

Re-ran:

```bash
pytest tests/test_equipment_progression.py -q
```

Result:

- `11 passed`
