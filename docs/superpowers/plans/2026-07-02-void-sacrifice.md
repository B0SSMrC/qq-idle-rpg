# Void Sacrifice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `虚空献祭` gold lottery with single draw, ten-draw, rarity pools, ten-draw `epic+` guarantee, and persistent `mythic+` / `divine` pity.

**Architecture:** Keep lottery math pure in `game_core/void_sacrifice.py`, persistence in `storage/void_sacrifice_repo.py`, player mutation and transactions in `app/services.py`, and chat output in `bot/formatting.py` plus `bot/plugins/rpg.py`. This mirrors the world Boss split while keeping spend logic behind the existing per-player bot lock.

**Tech Stack:** Python 3.12, SQLite, pytest, existing OneBot/NoneBot command plugin, existing `game_core.loot.add_item` affix generation.

## Global Constraints

- Command names: `虚空献祭`, `献祭`, `虚空献祭 10`, `献祭 10`, `十连献祭`, `献祭十连`.
- Only draw counts `1` and `10` are valid.
- Cost: one draw costs `1000` gold; ten draws cost `10000` gold.
- Base rates: common feedback `50.0%`, rare gear `25.0%`, epic gear `15.0%`, legendary gear `7.0%`, mythic gear `2.5%`, divine gear `0.5%`.
- Ten-draw guarantee: a ten-draw must contain at least one `epic+` reward.
- Pity scope: per `group_id + user_id`.
- Pity thresholds: `50` misses for `mythic+`, `120` misses for `divine`; divine pity has priority.
- Gear rewards use existing item definitions and receive affixes through the current loot system.
- No auto-equip, no draw history command, no paid currency.

---

## File Structure

- Create `game_core/void_sacrifice.py`: pure constants, reward pools, count parser, pity dataclass, draw dataclass, and draw rolling.
- Create `storage/void_sacrifice_repo.py`: SQLite load/save for pity state.
- Modify `storage/db.py`: create `void_sacrifice_pity` table in base schema.
- Modify `app/services.py`: add `do_void_sacrifice()` service, transactional gold deduction, reward grants, and pity persistence.
- Modify `bot/formatting.py`: add `render_void_sacrifice()` and rarity labels.
- Modify `bot/fuzzy_commands.py`: add safe explicit aliases for `虚空献祭`.
- Modify `bot/plugins/rpg.py`: register command handlers and fuzzy dispatch branch.
- Modify `docs/game-commands.md`: document commands, expected output, and errors.
- Add tests:
  - `tests/test_void_sacrifice_core.py`
  - `tests/test_void_sacrifice_db.py`
  - `tests/test_void_sacrifice_services.py`
  - extend `tests/test_formatting.py`
  - extend `tests/test_fuzzy_commands.py`

---

### Task 1: Core Lottery Logic

**Files:**
- Create: `game_core/void_sacrifice.py`
- Test: `tests/test_void_sacrifice_core.py`

**Interfaces:**
- Consumes: `GameConfig`, `random.Random`.
- Produces:
  - `VOID_SACRIFICE_SINGLE_COST: int`
  - `VOID_SACRIFICE_TEN_COST: int`
  - `MYTHIC_PLUS_PITY_THRESHOLD: int`
  - `DIVINE_PITY_THRESHOLD: int`
  - `VoidSacrificePity(total_draws: int = 0, draws_since_mythic_plus: int = 0, draws_since_divine: int = 0)`
  - `VoidSacrificeDraw(rarity: str, item_id: str = "", consumable_id: str = "", gold_refund: int = 0, guaranteed: bool = False, pity_trigger: str = "")`
  - `VoidSacrificeRoll(draws: list[VoidSacrificeDraw], pity: VoidSacrificePity, ten_draw_guarantee_triggered: bool)`
  - `parse_draw_count(arg: str) -> int`
  - `remaining_mythic_plus_pity(pity: VoidSacrificePity) -> int`
  - `remaining_divine_pity(pity: VoidSacrificePity) -> int`
  - `roll_void_sacrifice(draw_count: int, cfg: GameConfig, rng: random.Random, pity: VoidSacrificePity) -> VoidSacrificeRoll`

- [ ] **Step 1: Write the failing core tests**

Create `tests/test_void_sacrifice_core.py`:

```python
from __future__ import annotations

import random

import pytest

from game_core.config import load_config
from game_core.void_sacrifice import (
    DIVINE_PITY_THRESHOLD,
    MYTHIC_PLUS_PITY_THRESHOLD,
    VOID_SACRIFICE_SINGLE_COST,
    VOID_SACRIFICE_TEN_COST,
    VoidSacrificePity,
    parse_draw_count,
    remaining_divine_pity,
    remaining_mythic_plus_pity,
    roll_void_sacrifice,
)


CFG = load_config()


def test_void_sacrifice_constants_match_design():
    assert VOID_SACRIFICE_SINGLE_COST == 1000
    assert VOID_SACRIFICE_TEN_COST == 10000
    assert MYTHIC_PLUS_PITY_THRESHOLD == 50
    assert DIVINE_PITY_THRESHOLD == 120


@pytest.mark.parametrize(
    ("arg", "expected"),
    [
        ("", 1),
        ("1", 1),
        ("10", 10),
        ("十连", 10),
        ("献祭十连", 10),
    ],
)
def test_parse_draw_count_accepts_supported_forms(arg, expected):
    assert parse_draw_count(arg) == expected


@pytest.mark.parametrize("arg", ["2", "11", "abc", "三连"])
def test_parse_draw_count_rejects_unsupported_counts(arg):
    with pytest.raises(ValueError, match="用法:虚空献祭"):
        parse_draw_count(arg)


def test_single_draw_can_return_rare_gear_with_affix_target():
    roll = roll_void_sacrifice(
        1,
        CFG,
        random.Random(5),
        VoidSacrificePity(),
    )

    assert len(roll.draws) == 1
    assert roll.draws[0].rarity in {
        "common",
        "rare",
        "epic",
        "legendary",
        "mythic",
        "divine",
    }
    if roll.draws[0].rarity != "common":
        assert roll.draws[0].item_id in CFG.items
        assert CFG.items[roll.draws[0].item_id].slot in {"weapon", "armor"}


def test_ten_draw_guarantees_epic_plus_when_all_rolls_are_low(monkeypatch):
    class LowRng(random.Random):
        def random(self):
            return 0.10

        def choice(self, seq):
            return seq[0]

        def randint(self, a, b):
            return a

    roll = roll_void_sacrifice(10, CFG, LowRng(), VoidSacrificePity())

    assert len(roll.draws) == 10
    assert roll.ten_draw_guarantee_triggered is True
    assert any(d.rarity in {"epic", "legendary", "mythic", "divine"} for d in roll.draws)
    assert roll.draws[-1].rarity == "epic"
    assert roll.draws[-1].guaranteed is True


def test_mythic_pity_forces_mythic_and_resets_mythic_counter():
    pity = VoidSacrificePity(
        total_draws=50,
        draws_since_mythic_plus=MYTHIC_PLUS_PITY_THRESHOLD,
        draws_since_divine=50,
    )

    roll = roll_void_sacrifice(1, CFG, random.Random(1), pity)

    assert roll.draws[0].rarity == "mythic"
    assert roll.draws[0].pity_trigger == "mythic"
    assert roll.pity.draws_since_mythic_plus == 0
    assert roll.pity.draws_since_divine == 51


def test_divine_pity_forces_divine_and_resets_both_counters():
    pity = VoidSacrificePity(
        total_draws=120,
        draws_since_mythic_plus=MYTHIC_PLUS_PITY_THRESHOLD,
        draws_since_divine=DIVINE_PITY_THRESHOLD,
    )

    roll = roll_void_sacrifice(1, CFG, random.Random(1), pity)

    assert roll.draws[0].rarity == "divine"
    assert roll.draws[0].pity_trigger == "divine"
    assert roll.pity.draws_since_mythic_plus == 0
    assert roll.pity.draws_since_divine == 0


def test_remaining_pity_counts_down_to_zero():
    pity = VoidSacrificePity(total_draws=0, draws_since_mythic_plus=37, draws_since_divine=112)

    assert remaining_mythic_plus_pity(pity) == 13
    assert remaining_divine_pity(pity) == 8
```

- [ ] **Step 2: Run core tests to verify they fail**

Run:

```bash
python -m pytest tests/test_void_sacrifice_core.py -q
```

Expected: fail during import because `game_core.void_sacrifice` does not exist.

- [ ] **Step 3: Implement the pure core module**

Create `game_core/void_sacrifice.py`:

```python
from __future__ import annotations

import random
from dataclasses import dataclass, field

from game_core.models import GameConfig

VOID_SACRIFICE_SINGLE_COST = 1000
VOID_SACRIFICE_TEN_COST = 10000
MYTHIC_PLUS_PITY_THRESHOLD = 50
DIVINE_PITY_THRESHOLD = 120

RARITY_ORDER = {
    "common": 0,
    "rare": 1,
    "epic": 2,
    "legendary": 3,
    "mythic": 4,
    "divine": 5,
}

GEAR_POOLS = {
    "rare": [
        "moonsteel_sword",
        "scarlet_moon_blade",
        "silver_dragon_spear",
        "ghost_lotus_dart",
        "cloudweave_armor",
        "black_iron_plate",
    ],
    "epic": [
        "starforged_sword",
        "thunder_soul_sword",
        "cloud_splitter_blade",
        "thunderclap_blade",
        "tiger_roar_spear",
        "meteor_halberd",
        "black_rain_needles",
        "soul_lock_nails",
        "moonshadow_armor",
        "phoenix_feather_armor",
        "dragon_scale_plate",
        "thunder_plate",
    ],
    "legendary": [
        "sunfire_sword",
        "dragon_spine_blade",
        "sea_quelling_halberd",
        "starfall_needles",
        "star_silk_armor",
        "mountain_guard_plate",
    ],
    "mythic": [
        "void_cleaver_sword",
        "emperor_jade_sword",
        "blood_sea_blade",
        "heaven_cleaver_blade",
        "heaven_river_spear",
        "world_pillar_halberd",
        "nether_blossom_dart",
        "ten_thousand_venom_box",
        "mirage_armor",
        "immortal_cloud_robe",
        "basalt_king_plate",
        "demon_seal_plate",
    ],
    "divine": [
        "skyfall_sword",
        "king_hell_blade",
        "nine_suns_spear",
        "silent_ending_needles",
        "galaxy_robe",
        "heaven_fortress_plate",
    ],
}

COMMON_CONSUMABLE_POOL = [
    "hp_potion",
    "greater_hp_potion",
    "supreme_hp_potion",
    "atk_potion_major",
    "def_potion_major",
    "stamina_potion",
]


@dataclass(frozen=True)
class VoidSacrificePity:
    total_draws: int = 0
    draws_since_mythic_plus: int = 0
    draws_since_divine: int = 0


@dataclass(frozen=True)
class VoidSacrificeDraw:
    rarity: str
    item_id: str = ""
    consumable_id: str = ""
    gold_refund: int = 0
    guaranteed: bool = False
    pity_trigger: str = ""


@dataclass(frozen=True)
class VoidSacrificeRoll:
    draws: list[VoidSacrificeDraw] = field(default_factory=list)
    pity: VoidSacrificePity = field(default_factory=VoidSacrificePity)
    ten_draw_guarantee_triggered: bool = False


def parse_draw_count(arg: str) -> int:
    text = str(arg or "").strip()
    if text == "":
        return 1
    if text in {"1", "一", "一次", "单抽"}:
        return 1
    if text in {"10", "十", "十连", "10连", "十连献祭", "献祭十连"}:
        return 10
    raise ValueError("用法:虚空献祭 [次数]，支持 1 或 10")


def remaining_mythic_plus_pity(pity: VoidSacrificePity) -> int:
    return max(0, MYTHIC_PLUS_PITY_THRESHOLD - pity.draws_since_mythic_plus)


def remaining_divine_pity(pity: VoidSacrificePity) -> int:
    return max(0, DIVINE_PITY_THRESHOLD - pity.draws_since_divine)


def _existing_items(cfg: GameConfig, item_ids: list[str]) -> list[str]:
    return [item_id for item_id in item_ids if item_id in cfg.items]


def _gear_item_id(rarity: str, cfg: GameConfig, rng: random.Random) -> str:
    pool = _existing_items(cfg, GEAR_POOLS[rarity])
    if not pool:
        raise RuntimeError("虚空献祭奖池配置异常,请稍后再试。")
    return rng.choice(pool)


def _natural_rarity(rng: random.Random) -> str:
    value = rng.random()
    if value < 0.50:
        return "common"
    if value < 0.75:
        return "rare"
    if value < 0.90:
        return "epic"
    if value < 0.97:
        return "legendary"
    if value < 0.995:
        return "mythic"
    return "divine"


def _common_feedback(cfg: GameConfig, rng: random.Random) -> VoidSacrificeDraw:
    consumables = _existing_items(cfg, COMMON_CONSUMABLE_POOL)
    if consumables and rng.random() < 0.65:
        return VoidSacrificeDraw(rarity="common", consumable_id=rng.choice(consumables))
    return VoidSacrificeDraw(rarity="common", gold_refund=rng.randint(120, 320))


def _draw_for_rarity(
    rarity: str,
    cfg: GameConfig,
    rng: random.Random,
    *,
    guaranteed: bool = False,
    pity_trigger: str = "",
) -> VoidSacrificeDraw:
    if rarity == "common":
        draw = _common_feedback(cfg, rng)
        return VoidSacrificeDraw(
            rarity=draw.rarity,
            consumable_id=draw.consumable_id,
            gold_refund=draw.gold_refund,
            guaranteed=guaranteed,
            pity_trigger=pity_trigger,
        )
    return VoidSacrificeDraw(
        rarity=rarity,
        item_id=_gear_item_id(rarity, cfg, rng),
        guaranteed=guaranteed,
        pity_trigger=pity_trigger,
    )


def _apply_pity(pity: VoidSacrificePity, rarity: str) -> VoidSacrificePity:
    total = pity.total_draws + 1
    if rarity == "divine":
        return VoidSacrificePity(
            total_draws=total,
            draws_since_mythic_plus=0,
            draws_since_divine=0,
        )
    if rarity == "mythic":
        return VoidSacrificePity(
            total_draws=total,
            draws_since_mythic_plus=0,
            draws_since_divine=pity.draws_since_divine + 1,
        )
    return VoidSacrificePity(
        total_draws=total,
        draws_since_mythic_plus=pity.draws_since_mythic_plus + 1,
        draws_since_divine=pity.draws_since_divine + 1,
    )


def roll_void_sacrifice(
    draw_count: int,
    cfg: GameConfig,
    rng: random.Random,
    pity: VoidSacrificePity,
) -> VoidSacrificeRoll:
    if draw_count not in {1, 10}:
        raise ValueError("用法:虚空献祭 [次数]，支持 1 或 10")

    current_pity = pity
    draws: list[VoidSacrificeDraw] = []
    for draw_index in range(draw_count):
        pity_trigger = ""
        guaranteed = False
        if current_pity.draws_since_divine >= DIVINE_PITY_THRESHOLD:
            rarity = "divine"
            pity_trigger = "divine"
            guaranteed = True
        elif current_pity.draws_since_mythic_plus >= MYTHIC_PLUS_PITY_THRESHOLD:
            rarity = "mythic"
            pity_trigger = "mythic"
            guaranteed = True
        else:
            rarity = _natural_rarity(rng)

        is_last_ten_draw = draw_count == 10 and draw_index == 9
        has_epic_plus = any(RARITY_ORDER[d.rarity] >= RARITY_ORDER["epic"] for d in draws)
        ten_draw_guarantee = (
            is_last_ten_draw
            and not has_epic_plus
            and RARITY_ORDER[rarity] < RARITY_ORDER["epic"]
        )
        if ten_draw_guarantee:
            rarity = "epic"
            guaranteed = True

        draw = _draw_for_rarity(
            rarity,
            cfg,
            rng,
            guaranteed=guaranteed,
            pity_trigger=pity_trigger,
        )
        draws.append(draw)
        current_pity = _apply_pity(current_pity, draw.rarity)

    return VoidSacrificeRoll(
        draws=draws,
        pity=current_pity,
        ten_draw_guarantee_triggered=any(
            d.guaranteed and d.pity_trigger == "" and d.rarity == "epic"
            for d in draws
        ),
    )
```

- [ ] **Step 4: Run core tests to verify they pass**

Run:

```bash
python -m pytest tests/test_void_sacrifice_core.py -q
```

Expected: all tests in `tests/test_void_sacrifice_core.py` pass.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add game_core/void_sacrifice.py tests/test_void_sacrifice_core.py
git commit -m "feat: add void sacrifice core"
```

---

### Task 2: Pity Persistence

**Files:**
- Modify: `storage/db.py`
- Create: `storage/void_sacrifice_repo.py`
- Test: `tests/test_void_sacrifice_db.py`

**Interfaces:**
- Consumes: `VoidSacrificePity` from `game_core.void_sacrifice`.
- Produces:
  - `storage.void_sacrifice_repo.get_pity(conn, group_id: str, user_id: str) -> VoidSacrificePity`
  - `storage.void_sacrifice_repo.save_pity(conn, group_id: str, user_id: str, pity: VoidSacrificePity, now: int) -> None`

- [ ] **Step 1: Write failing persistence tests**

Create `tests/test_void_sacrifice_db.py`:

```python
from game_core.void_sacrifice import VoidSacrificePity
from storage import db, void_sacrifice_repo


def test_init_db_creates_void_sacrifice_pity_table():
    conn = db.get_conn(":memory:")
    db.init_db(conn)

    tables = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }

    assert "void_sacrifice_pity" in tables


def test_get_pity_returns_zero_state_before_first_draw():
    conn = db.get_conn(":memory:")
    db.init_db(conn)

    pity = void_sacrifice_repo.get_pity(conn, "g1", "u1")

    assert pity == VoidSacrificePity()


def test_save_pity_is_scoped_by_group_and_user():
    conn = db.get_conn(":memory:")
    db.init_db(conn)

    void_sacrifice_repo.save_pity(
        conn,
        "g1",
        "u1",
        VoidSacrificePity(total_draws=12, draws_since_mythic_plus=7, draws_since_divine=12),
        now=1000,
    )
    void_sacrifice_repo.save_pity(
        conn,
        "g2",
        "u1",
        VoidSacrificePity(total_draws=3, draws_since_mythic_plus=3, draws_since_divine=3),
        now=1001,
    )

    assert void_sacrifice_repo.get_pity(conn, "g1", "u1") == VoidSacrificePity(
        total_draws=12,
        draws_since_mythic_plus=7,
        draws_since_divine=12,
    )
    assert void_sacrifice_repo.get_pity(conn, "g2", "u1") == VoidSacrificePity(
        total_draws=3,
        draws_since_mythic_plus=3,
        draws_since_divine=3,
    )
```

- [ ] **Step 2: Run persistence tests to verify they fail**

Run:

```bash
python -m pytest tests/test_void_sacrifice_db.py -q
```

Expected: fail because `storage.void_sacrifice_repo` does not exist or the table is missing.

- [ ] **Step 3: Add the database table**

In `storage/db.py`, add this SQL block inside `SCHEMA` after `world_boss_rewards`:

```sql

CREATE TABLE IF NOT EXISTS void_sacrifice_pity (
    group_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    total_draws INTEGER NOT NULL DEFAULT 0,
    draws_since_mythic_plus INTEGER NOT NULL DEFAULT 0,
    draws_since_divine INTEGER NOT NULL DEFAULT 0,
    updated_at INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (group_id, user_id)
);
```

- [ ] **Step 4: Implement the pity repository**

Create `storage/void_sacrifice_repo.py`:

```python
from __future__ import annotations

import sqlite3

from game_core.void_sacrifice import VoidSacrificePity


def get_pity(conn: sqlite3.Connection, group_id: str, user_id: str) -> VoidSacrificePity:
    row = conn.execute(
        """
        SELECT * FROM void_sacrifice_pity
        WHERE group_id=? AND user_id=?
        """,
        (group_id, user_id),
    ).fetchone()
    if row is None:
        return VoidSacrificePity()
    return VoidSacrificePity(
        total_draws=int(row["total_draws"]),
        draws_since_mythic_plus=int(row["draws_since_mythic_plus"]),
        draws_since_divine=int(row["draws_since_divine"]),
    )


def save_pity(
    conn: sqlite3.Connection,
    group_id: str,
    user_id: str,
    pity: VoidSacrificePity,
    now: int,
) -> None:
    conn.execute(
        """
        INSERT INTO void_sacrifice_pity (
            group_id,user_id,total_draws,draws_since_mythic_plus,draws_since_divine,updated_at
        ) VALUES (?,?,?,?,?,?)
        ON CONFLICT(group_id, user_id) DO UPDATE SET
            total_draws=excluded.total_draws,
            draws_since_mythic_plus=excluded.draws_since_mythic_plus,
            draws_since_divine=excluded.draws_since_divine,
            updated_at=excluded.updated_at
        """,
        (
            group_id,
            user_id,
            pity.total_draws,
            pity.draws_since_mythic_plus,
            pity.draws_since_divine,
            now,
        ),
    )
```

- [ ] **Step 5: Run persistence tests to verify they pass**

Run:

```bash
python -m pytest tests/test_void_sacrifice_db.py -q
```

Expected: all tests in `tests/test_void_sacrifice_db.py` pass.

- [ ] **Step 6: Commit Task 2**

Run:

```bash
git add storage/db.py storage/void_sacrifice_repo.py tests/test_void_sacrifice_db.py
git commit -m "feat: persist void sacrifice pity"
```

---

### Task 3: Service Transaction and Reward Grants

**Files:**
- Modify: `app/services.py`
- Test: `tests/test_void_sacrifice_services.py`

**Interfaces:**
- Consumes:
  - `roll_void_sacrifice(draw_count, cfg, rng, pity) -> VoidSacrificeRoll`
  - `void_sacrifice_repo.get_pity()`
  - `void_sacrifice_repo.save_pity()`
  - `loot.add_item()` for consumables and gear affixes.
- Produces:
  - `VoidSacrificeResult(player: Player, draw_count: int, cost: int, draws: list[VoidSacrificeDraw], pity: VoidSacrificePity, ten_draw_guarantee_triggered: bool)`
  - `do_void_sacrifice(conn, cfg, group_id, user_id, draw_count, now, rng) -> VoidSacrificeResult`

- [ ] **Step 1: Write failing service tests**

Create `tests/test_void_sacrifice_services.py`:

```python
from __future__ import annotations

import random

import pytest

from app import services
from game_core.config import load_config
from game_core.errors import GameError, NotEnoughGold
from game_core.models import Player
from game_core.void_sacrifice import VoidSacrificePity
from storage import db, repository as repo, void_sacrifice_repo


CFG = load_config()


def _conn():
    conn = db.get_conn(":memory:")
    db.init_db(conn)
    return conn


def _player(conn, *, gold=20000, group_id="g", user_id="u"):
    player = Player(
        group_id=group_id,
        user_id=user_id,
        name=f"p-{group_id}-{user_id}",
        gold=gold,
        stamina=100,
        stamina_at=1000,
        current_hp=100,
        created_at=1000,
        last_active_at=1000,
    )
    return repo.create_player(conn, player)


def test_do_void_sacrifice_single_draw_deducts_gold_and_persists_pity():
    conn = _conn()
    _player(conn, gold=20000)

    result = services.do_void_sacrifice(
        conn, CFG, "g", "u", 1, now=2000, rng=random.Random(5)
    )

    saved = repo.get_player(conn, "g", "u")
    pity = void_sacrifice_repo.get_pity(conn, "g", "u")
    assert result.cost == 1000
    assert result.draw_count == 1
    assert len(result.draws) == 1
    assert saved.gold == result.player.gold
    assert saved.gold <= 19000 + 320
    assert pity.total_draws == 1


def test_do_void_sacrifice_ten_draw_deducts_gold_and_grants_ten_entries():
    conn = _conn()
    _player(conn, gold=20000)

    result = services.do_void_sacrifice(
        conn, CFG, "g", "u", 10, now=2000, rng=random.Random(3)
    )

    assert result.cost == 10000
    assert result.draw_count == 10
    assert len(result.draws) == 10
    assert result.pity.total_draws == 10
    assert any(d.rarity in {"epic", "legendary", "mythic", "divine"} for d in result.draws)


def test_do_void_sacrifice_insufficient_gold_deducts_nothing_and_keeps_pity():
    conn = _conn()
    _player(conn, gold=999)

    with pytest.raises(NotEnoughGold, match="金币不足"):
        services.do_void_sacrifice(conn, CFG, "g", "u", 1, now=2000, rng=random.Random(1))

    saved = repo.get_player(conn, "g", "u")
    pity = void_sacrifice_repo.get_pity(conn, "g", "u")
    assert saved.gold == 999
    assert pity == VoidSacrificePity()


def test_do_void_sacrifice_rejects_invalid_count():
    conn = _conn()
    _player(conn, gold=20000)

    with pytest.raises(GameError, match="用法:虚空献祭"):
        services.do_void_sacrifice(conn, CFG, "g", "u", 2, now=2000, rng=random.Random(1))


def test_do_void_sacrifice_pity_is_scoped_by_group_and_user():
    conn = _conn()
    _player(conn, gold=20000, group_id="g1", user_id="u")
    _player(conn, gold=20000, group_id="g2", user_id="u")

    services.do_void_sacrifice(conn, CFG, "g1", "u", 1, now=2000, rng=random.Random(1))

    assert void_sacrifice_repo.get_pity(conn, "g1", "u").total_draws == 1
    assert void_sacrifice_repo.get_pity(conn, "g2", "u").total_draws == 0
```

- [ ] **Step 2: Run service tests to verify they fail**

Run:

```bash
python -m pytest tests/test_void_sacrifice_services.py -q
```

Expected: fail because `services.do_void_sacrifice` does not exist.

- [ ] **Step 3: Add service imports and result dataclass**

In `app/services.py`, add `void_sacrifice_repo` to the storage import area:

```python
from storage import void_sacrifice_repo
```

Add this import beside the world Boss import block:

```python
from game_core.void_sacrifice import (
    VOID_SACRIFICE_SINGLE_COST,
    VOID_SACRIFICE_TEN_COST,
    VoidSacrificeDraw,
    VoidSacrificePity,
    parse_draw_count,
    roll_void_sacrifice,
)
```

Add this dataclass after `WorldBossAttackResult`:

```python
@dataclass
class VoidSacrificeResult:
    player: Player
    draw_count: int
    cost: int
    draws: list[VoidSacrificeDraw]
    pity: VoidSacrificePity
    ten_draw_guarantee_triggered: bool = False
```

- [ ] **Step 4: Implement `do_void_sacrifice`**

Add this function before `do_explore()` in `app/services.py`:

```python
def do_void_sacrifice(conn, cfg, group_id, user_id, draw_count, now, rng) -> VoidSacrificeResult:
    try:
        count = parse_draw_count(str(draw_count))
    except ValueError as exc:
        raise GameError(str(exc)) from exc
    cost = VOID_SACRIFICE_TEN_COST if count == 10 else VOID_SACRIFICE_SINGLE_COST

    player = _require(conn, cfg, group_id, user_id)
    if player.gold < cost:
        raise NotEnoughGold(f"金币不足(需 {cost},当前 {player.gold})")

    try:
        conn.execute("BEGIN IMMEDIATE")
        fresh_player = _require(conn, cfg, group_id, user_id)
        if fresh_player.gold < cost:
            raise NotEnoughGold(f"金币不足(需 {cost},当前 {fresh_player.gold})")
        pity = void_sacrifice_repo.get_pity(conn, group_id, user_id)
        roll = roll_void_sacrifice(count, cfg, rng, pity)

        fresh_player.gold -= cost
        for draw in roll.draws:
            if draw.gold_refund > 0:
                fresh_player.gold += draw.gold_refund
            if draw.consumable_id:
                _loot.add_item(fresh_player, draw.consumable_id, cfg=cfg, rng=rng)
            if draw.item_id:
                _loot.add_item(fresh_player, draw.item_id, cfg=cfg, rng=rng)
        fresh_player.last_active_at = now

        repo.save_player(conn, fresh_player, commit=False)
        void_sacrifice_repo.save_pity(conn, group_id, user_id, roll.pity, now)
        conn.commit()
        return VoidSacrificeResult(
            player=fresh_player,
            draw_count=count,
            cost=cost,
            draws=roll.draws,
            pity=roll.pity,
            ten_draw_guarantee_triggered=roll.ten_draw_guarantee_triggered,
        )
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
```

- [ ] **Step 5: Run service tests to verify they pass**

Run:

```bash
python -m pytest tests/test_void_sacrifice_services.py -q
```

Expected: all service tests pass.

- [ ] **Step 6: Commit Task 3**

Run:

```bash
git add app/services.py tests/test_void_sacrifice_services.py
git commit -m "feat: add void sacrifice service"
```

---

### Task 4: Bot Commands, Formatting, Fuzzy Routing, and Docs

**Files:**
- Modify: `bot/formatting.py`
- Modify: `bot/fuzzy_commands.py`
- Modify: `bot/plugins/rpg.py`
- Modify: `docs/game-commands.md`
- Test: `tests/test_formatting.py`
- Test: `tests/test_fuzzy_commands.py`

**Interfaces:**
- Consumes:
  - `services.do_void_sacrifice(conn, cfg, group_id, user_id, draw_count, now, rng) -> VoidSacrificeResult`
  - `parse_draw_count(arg: str) -> int`
- Produces:
  - `render_void_sacrifice(result, cfg: GameConfig) -> str`
  - fuzzy command id `void_sacrifice`
  - command handler for `虚空献祭` and aliases.

- [ ] **Step 1: Write failing formatting and fuzzy tests**

Append to `tests/test_formatting.py`:

```python
from app.services import VoidSacrificeResult
from game_core.models import Player
from game_core.void_sacrifice import VoidSacrificeDraw, VoidSacrificePity
from bot.formatting import render_void_sacrifice


def test_render_void_sacrifice_lists_rewards_and_pity():
    result = VoidSacrificeResult(
        player=Player(group_id="g", user_id="u", name="cxh", gold=9000),
        draw_count=10,
        cost=10000,
        draws=[
            VoidSacrificeDraw(rarity="common", consumable_id="def_potion_major"),
            VoidSacrificeDraw(rarity="epic", item_id="thunder_plate", guaranteed=True),
            VoidSacrificeDraw(rarity="common", gold_refund=240),
        ],
        pity=VoidSacrificePity(total_draws=10, draws_since_mythic_plus=10, draws_since_divine=10),
        ten_draw_guarantee_triggered=True,
    )

    text = render_void_sacrifice(result, CFG)

    assert "🌌 虚空献祭 ×10" in text
    assert "消耗金币:10000" in text
    assert "金钟罩符 ×1" in text
    assert "雷纹锁子甲" in text
    assert "epic" in text
    assert "返还金币 240" in text
    assert "十连保底已生效" in text
    assert "距 mythic+ 保底:40抽" in text
    assert "距 divine 保底:110抽" in text
```

Append to `tests/test_fuzzy_commands.py`:

```python
def test_fuzzy_void_sacrifice_aliases():
    assert parse_fuzzy_command("虚空献祭").command == "void_sacrifice"
    assert parse_fuzzy_command("献祭").command == "void_sacrifice"
    assert parse_fuzzy_command("虚空献祭10").arg == "10"
    assert parse_fuzzy_command("十连献祭").arg == "10"
```

- [ ] **Step 2: Run formatting and fuzzy tests to verify they fail**

Run:

```bash
python -m pytest tests/test_formatting.py::test_render_void_sacrifice_lists_rewards_and_pity tests/test_fuzzy_commands.py::test_fuzzy_void_sacrifice_aliases -q
```

Expected: fail because `render_void_sacrifice` and fuzzy route do not exist.

- [ ] **Step 3: Implement formatter**

In `bot/formatting.py`, import pity helpers:

```python
from game_core.void_sacrifice import (
    remaining_divine_pity,
    remaining_mythic_plus_pity,
)
```

Add this function near the other renderers:

```python
def render_void_sacrifice(result, cfg: GameConfig) -> str:
    lines = [
        f"🌌 虚空献祭 ×{result.draw_count}",
        f"消耗金币:{result.cost}",
        "",
    ]
    for index, draw in enumerate(result.draws, start=1):
        if draw.item_id:
            item_name = _item_name(cfg, draw.item_id)
            affix = ""
            for inv in reversed(result.player.inventory):
                if inv.item_id == draw.item_id:
                    affix = format_affix(inv.affix)
                    break
            affix_text = f"[{affix}]" if affix else ""
            lines.append(f"{index}. {item_name}{affix_text}  {draw.rarity}")
        elif draw.consumable_id:
            lines.append(f"{index}. {_item_name(cfg, draw.consumable_id)} ×1")
        elif draw.gold_refund > 0:
            lines.append(f"{index}. 返还金币 {draw.gold_refund}")
        else:
            lines.append(f"{index}. 虚空回声散去")
    if result.ten_draw_guarantee_triggered:
        lines.extend(["", "✨ 十连保底已生效: epic+"])
    lines.extend([
        f"🔮 距 mythic+ 保底:{remaining_mythic_plus_pity(result.pity)}抽",
        f"🌠 距 divine 保底:{remaining_divine_pity(result.pity)}抽",
    ])
    return "\n".join(lines)
```

- [ ] **Step 4: Implement fuzzy aliases**

In `bot/fuzzy_commands.py`, add these `_AliasRule` entries before `buy` aliases so `献祭` does not fall through to unknown:

```python
    _AliasRule("void_sacrifice", "十连献祭", arg="10", no_arg_only=True, fuzzy=False),
    _AliasRule("void_sacrifice", "献祭十连", arg="10", no_arg_only=True, fuzzy=False),
    _AliasRule("void_sacrifice", "虚空献祭", requires_arg=False, fuzzy=False),
    _AliasRule("void_sacrifice", "献祭", requires_arg=False, fuzzy=False),
```

If `_AliasRule` does not support a fixed `arg`, use the existing dataclass shape and implement this explicit branch in `parse_fuzzy_command()` before iterating rules:

```python
    if text in {"十连献祭", "献祭十连"}:
        return ParsedCommand("void_sacrifice", "10")
```

- [ ] **Step 5: Implement bot command handler**

In `bot/plugins/rpg.py`, add `render_void_sacrifice` to the formatting imports:

```python
    render_void_sacrifice,
```

Add this import:

```python
from game_core.void_sacrifice import parse_draw_count
```

Add command block before the world Boss section:

```python
cmd_void_sacrifice = on_command(
    "虚空献祭",
    aliases={"献祭", "十连献祭", "献祭十连"},
    rule=to_me(),
    priority=10,
    block=True,
)


async def _handle_void_sacrifice_arg(bot: Bot, event: Event, arg: str):
    text = str(arg or "").strip()
    if event.get_plaintext().strip() in {"十连献祭", "/十连献祭", "献祭十连", "/献祭十连"}:
        text = "10"
    try:
        draw_count = parse_draw_count(text)
    except ValueError as e:
        await _reply(bot, event, str(e))
        return
    gid, uid = _scope(event)

    async def _do():
        async with state.player_lock(gid, uid):
            result = services.do_void_sacrifice(
                state.conn(), state.CFG, gid, uid, draw_count, state.now(), random.Random()
            )
            await _reply_to(
                bot,
                event,
                result.player.name,
                render_void_sacrifice(result, state.CFG),
            )

    await _guard(bot, event, _do())


@cmd_void_sacrifice.handle()
async def handle_void_sacrifice(bot: Bot, event: Event):
    await _handle_void_sacrifice_arg(
        bot,
        event,
        _arg(event, "虚空献祭", "献祭", "十连献祭", "献祭十连"),
    )
```

Add this branch to `handle_fuzzy()` before world Boss branches:

```python
    elif parsed.command == "void_sacrifice":
        await _handle_void_sacrifice_arg(bot, event, parsed.arg)
```

Add help text lines:

```text
虚空献祭 [1/10] — 花金币献祭抽取装备
```

- [ ] **Step 6: Update command docs**

In `docs/game-commands.md`, add `虚空献祭` to the command overview and help output. Add a section:

````markdown
## 虚空献祭

示例：

```text
虚空献祭
献祭
虚空献祭 10
十连献祭
```

规则说明：
- 单抽消耗 1000 金币，10 连消耗 10000 金币。
- 只支持 1 抽和 10 抽。
- 10 连至少获得 1 件 epic+ 装备。
- 50 抽未出 mythic+ 时，下一次触发 mythic+ 保底。
- 120 抽未出 divine 时，下一次触发 divine 保底。
- 获得武器和防具会自动生成词条。

预期输出：

```text
「cxh」
🌌 虚空献祭 ×10
消耗金币:10000

1. 金钟罩符 ×1
2. 雷纹锁子甲[厚血(生命+14%)]  epic
3. 返还金币 240

🔮 距 mythic+ 保底:40抽
🌠 距 divine 保底:110抽
```

常见错误：

```text
用法:虚空献祭 [次数]，支持 1 或 10
金币不足(需 10000,当前 3719)
你在当前世界还没有角色,先发「注册 角色名」吧~
```
````

- [ ] **Step 7: Run bot-facing tests**

Run:

```bash
python -m pytest tests/test_formatting.py::test_render_void_sacrifice_lists_rewards_and_pity tests/test_fuzzy_commands.py::test_fuzzy_void_sacrifice_aliases -q
```

Expected: both tests pass.

- [ ] **Step 8: Commit Task 4**

Run:

```bash
git add bot/formatting.py bot/fuzzy_commands.py bot/plugins/rpg.py docs/game-commands.md tests/test_formatting.py tests/test_fuzzy_commands.py
git commit -m "feat: add void sacrifice bot command"
```

---

### Task 5: Final Integration Verification

**Files:**
- No new production files.
- Validate all files touched by Tasks 1-4.

**Interfaces:**
- Consumes all previous tasks.
- Produces a verified branch ready to push.

- [ ] **Step 1: Run focused void sacrifice tests**

Run:

```bash
python -m pytest tests/test_void_sacrifice_core.py tests/test_void_sacrifice_db.py tests/test_void_sacrifice_services.py -q
```

Expected: all focused void sacrifice tests pass.

- [ ] **Step 2: Run full test suite**

Run:

```bash
python -m pytest -q
```

Expected: full suite passes.

- [ ] **Step 3: Run compile check**

Run:

```bash
python -m compileall -q bot app game_core storage
```

Expected: exit code `0`.

- [ ] **Step 4: Run whitespace check**

Run:

```bash
git diff --check
```

Expected: no whitespace errors. Windows CRLF warnings are acceptable if there are no error lines.

- [ ] **Step 5: Review final diff**

Run:

```bash
git status --short
git diff --stat
```

Expected: working tree contains only intended void sacrifice files if there are uncommitted changes; otherwise clean after task commits.

- [ ] **Step 6: Push after user approval**

If the user asks to push, run:

```bash
git push origin main
```

Expected: `main -> main` push succeeds.

---

## Self-Review Notes

- Spec coverage: commands, cost, base rates, ten-draw guarantee, pity priority, gear pools, persistence, service flow, output, errors, and tests are each mapped to tasks above.
- Placeholder scan: the plan contains concrete commands, code snippets, and expected results for each task.
- Type consistency: `VoidSacrificePity`, `VoidSacrificeDraw`, `VoidSacrificeRoll`, `VoidSacrificeResult`, `roll_void_sacrifice`, `do_void_sacrifice`, and `render_void_sacrifice` are defined before later tasks consume them.
