# Task 3 Report: Apply Growth Stats and Update Displays

## Implementation Summary

- Updated `game_core/stats.py` so equipped gear contributes progression-adjusted attack, defense, and HP via `gear_growth_stats(inv, item)` before affix modifiers are applied.
- Updated `bot/formatting.py` to:
  - show enhancement/star labels on equipped gear in status and inventory text,
  - render progression-adjusted gear stat summaries in inventory/status displays,
  - label material items as `材料`.
- Updated `bot/inventory_image.py` to:
  - append enhancement/star labels to weapon/armor row names,
  - render progression-adjusted gear stats in image rows,
  - label materials as `材料`.
- Added targeted regression tests in:
  - `tests/test_stats.py`
  - `tests/test_formatting.py`
  - `tests/test_inventory_image.py`

## RED / GREEN TDD Evidence

### RED

Added these tests first:

- `tests/test_stats.py::test_equipment_growth_increases_player_stats_before_affixes`
- `tests/test_formatting.py::test_render_status_shows_equipment_growth_labels`
- `tests/test_formatting.py::test_render_inventory_shows_material_description`
- `tests/test_inventory_image.py::test_inventory_image_rows_show_equipment_growth_and_materials`

Ran:

```bash
pytest tests/test_stats.py::test_equipment_growth_increases_player_stats_before_affixes tests/test_formatting.py::test_render_status_shows_equipment_growth_labels tests/test_formatting.py::test_render_inventory_shows_material_description tests/test_inventory_image.py::test_inventory_image_rows_show_equipment_growth_and_materials -q
```

Observed initial failure state:

- 4 collected, 4 failed.
- Failures showed:
  - player defense/HP/attack were not using growth-adjusted gear stats,
  - status text did not show enhancement/star labels,
  - inventory text did not describe materials,
  - inventory image rows did not show growth labels/material tags.

During GREEN work, one intermediate run exposed a circular import (`stats -> equipment_progression -> loot -> stats`). I resolved that by using a lazy helper import inside `game_core/stats.py` instead of a module-level import.

### GREEN

Re-ran the same focused command after implementation:

```bash
pytest tests/test_stats.py::test_equipment_growth_increases_player_stats_before_affixes tests/test_formatting.py::test_render_status_shows_equipment_growth_labels tests/test_formatting.py::test_render_inventory_shows_material_description tests/test_inventory_image.py::test_inventory_image_rows_show_equipment_growth_and_materials -q
```

Result:

- 4 collected, 4 passed.

## Tests Run With Results

### 1. Focused RED verification

```bash
pytest tests/test_stats.py::test_equipment_growth_increases_player_stats_before_affixes tests/test_formatting.py::test_render_status_shows_equipment_growth_labels tests/test_formatting.py::test_render_inventory_shows_material_description tests/test_inventory_image.py::test_inventory_image_rows_show_equipment_growth_and_materials -q
```

Result:

- First run: 4 failed.
- Final run: 4 passed.

### 2. Scoped verification before completion

```bash
pytest tests/test_stats.py tests/test_formatting.py tests/test_inventory_image.py -q
```

Result:

- 34 passed in 0.55s.

## Files Changed

- `game_core/stats.py`
- `bot/formatting.py`
- `bot/inventory_image.py`
- `tests/test_stats.py`
- `tests/test_formatting.py`
- `tests/test_inventory_image.py`

## Self-Review

- Scope stayed within the six allowed implementation/test files.
- No services, commands, routing, reward-pool, or docs changes were added.
- Existing status/inventory/image tests remained green after the update.
- The circular import introduced by the straightforward module import was corrected without expanding scope.
- Display helpers were shared enough to keep status/inventory output behavior aligned.

## Concerns

- `bot/formatting.py` and some adjacent display files already contain mixed historical encoding artifacts. I kept the behavioral changes localized and used stable Unicode escapes where helpful, but that file would benefit from a future encoding cleanup outside this task's scope.
