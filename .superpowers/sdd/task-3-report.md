# Task 3 Report: Service Transaction and Reward Grants

## Status

DONE

## Scope Completed

- Added `VoidSacrificeResult` to `app/services.py`.
- Implemented `services.do_void_sacrifice(...)` with:
  - draw-count parsing through `parse_draw_count`
  - cost selection for single and ten draws
  - preflight and in-transaction gold validation
  - pity load via `void_sacrifice_repo.get_pity(...)`
  - reward rolling via `roll_void_sacrifice(...)`
  - reward grants through existing `_loot.add_item(...)` path
  - gold refunds applied per draw
  - player save and pity save inside one `BEGIN IMMEDIATE` transaction
  - rollback on failure
- Added `tests/test_void_sacrifice_services.py` covering:
  - single draw cost, persistence, and pity update
  - ten draw cost and reward count
  - insufficient-gold rollback behavior
  - invalid draw-count rejection
  - pity scoping by `group_id` and `user_id`

## TDD Flow

1. Added the new service test file first.
2. Ran `python -m pytest tests/test_void_sacrifice_services.py -q`.
3. Fixed test setup drift to match current `load_config(Path("data"))` signature.
4. Re-ran and verified RED against missing `services.do_void_sacrifice`.
5. Implemented the service code in `app/services.py`.
6. Re-ran the service test file to verify GREEN.

## Verification

- `python -m pytest tests/test_void_sacrifice_services.py -q`
  - Result: 5 passed
- `python -m pytest tests/test_void_sacrifice_services.py tests/test_void_sacrifice_core.py tests/test_void_sacrifice_db.py tests/test_world_boss_services.py -q`
  - Result: 35 passed

## Notes

- I left unrelated untracked `.superpowers/sdd/*` files untouched.
- The new tests had to use `load_config(Path("data"))` because the current repository signature differs from the brief’s shorthand `load_config()`. This was a test-fixture compatibility adjustment only; the service behavior remains aligned with the task brief.

## Files Changed

- `app/services.py`
- `tests/test_void_sacrifice_services.py`
- `.superpowers/sdd/task-3-report.md`
