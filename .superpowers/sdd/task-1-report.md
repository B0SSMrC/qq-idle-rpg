Status: DONE

Commits created:
- 4a46ad: feat: add void sacrifice core

One-line test summary: `python -m pytest tests/test_void_sacrifice_core.py -q` -> `20 passed`

Concerns:
- None.

Report file path:
- `.superpowers/sdd/task-1-report.md`

Task-1 fix pass:

Fixes made:
- Tightened `parse_draw_count` in `game_core/void_sacrifice.py` to accept only:
  - empty string (`""`) -> `1`
  - `"1"` -> `1`
  - full ten-draw command forms `十连献祭` / `献祭十连` -> `10`
- Updated `tests/test_void_sacrifice_core.py` to use the actual current config signature directly:
  - `CFG = load_config(Path("data"))`
- Updated draw-count tests to assert rejection of disallowed aliases (`"十"`, `"十连"`, `"10连"`, `"一"`, `"一次"`, `"单抽"`).

Files changed:
- `game_core/void_sacrifice.py`
- `tests/test_void_sacrifice_core.py`
- `.superpowers/sdd/task-1-report.md`
