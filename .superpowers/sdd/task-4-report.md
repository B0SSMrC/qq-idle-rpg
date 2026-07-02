Status: DONE
Commits created:
- feat: add void sacrifice bot command
- docs: add task 4 report
One-line test summary: `python -m pytest tests/test_formatting.py::test_render_void_sacrifice_lists_rewards_and_pity tests/test_fuzzy_commands.py::test_fuzzy_void_sacrifice_aliases -q` passed (2/2), and `python -m py_compile bot/formatting.py bot/fuzzy_commands.py bot/plugins/rpg.py tests/test_formatting.py tests/test_fuzzy_commands.py` passed.
Concerns: None.
Report file path: `D:\Claude Code\qq-idle-rpg\.superpowers\sdd\task-4-report.md`

Note: 2026-07-02 - This task-4 report was intentionally untracked again via git rm --cached .superpowers/sdd/task-4-report.md. Command evidence: git status --short shows D .superpowers/sdd/task-4-report.md (staged removal) and ?? .superpowers/sdd/task-4-report.md (local scratch file present for controller/reviewer).

## 2026-07-02 Duplicate Affix Review Fix

Fixes made
- Added `test_render_void_sacrifice_uses_distinct_affixes_for_duplicate_gear` to cover two `thunder_plate` drops with different inventory affixes.
- Updated `render_void_sacrifice()` to queue matching inventory entries by `item_id` and consume them once per gear draw in draw order.
- Left the rendered line format unchanged outside the affix-to-drop matching fix.

Covering test commands and results
- `python -m pytest tests/test_formatting.py::test_render_void_sacrifice_lists_rewards_and_pity tests/test_formatting.py::test_render_void_sacrifice_uses_distinct_affixes_for_duplicate_gear -q` -> passed (`2 passed`)
- `python -m pytest tests/test_formatting.py tests/test_fuzzy_commands.py -q` -> passed (`23 passed`)

Files changed
- `bot/formatting.py`
- `tests/test_formatting.py`
- `.superpowers/sdd/task-4-report.md`
