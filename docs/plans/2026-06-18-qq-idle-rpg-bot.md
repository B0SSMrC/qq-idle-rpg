# QQ 文字挂机探索 RPG —— 存储 + 机器人接入(计划二)实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在已完成的纯引擎 `game_core` 之上,加一层 SQLite 持久化、一层不依赖 NoneBot 的服务用例层、一层中文消息格式化,最后用 NoneBot2 + 官方 QQ 适配器把它接成能在沙箱频道/群里玩的机器人。

**Architecture:** 依赖方向 `bot → app(services) → game_core + storage`。`storage` 负责 SQLite 读写(同步 `sqlite3`);`app/services.py` 编排"读档→调引擎系统→存档"的用例,纯函数式(传入 conn/cfg/now/rng,可用内存 DB 单测);`bot/formatting.py` 是唯一把引擎结果对象渲染成中文文本的地方;`bot/` 插件极薄,只做"解析指令→调 service→回消息",并集中处理异常不外泄。

**Tech Stack:** Python 3.10+、标准库 `sqlite3`、NoneBot2、nonebot-adapter-qq、pytest。

前置:计划一已完成并合并到 master(`game_core` 引擎,53 测试全绿)。参考设计文档:`docs/specs/2026-06-18-qq-idle-rpg-design.md`。

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `storage/__init__.py` | 包标记 |
| `storage/db.py` | SQLite 连接工厂 + 建表(schema) |
| `storage/repository.py` | Player/inventory 的读写、群成员列表查询 |
| `app/__init__.py` | 包标记 |
| `app/services.py` | 用例层:register/explore/status/equip/use/buy/ranking,中文名解析 |
| `bot/__init__.py` | NoneBot 初始化 + 适配器注册 + 全局 conn/cfg |
| `bot/formatting.py` | 结果对象 → 中文消息文本(唯一排版处) |
| `bot/plugins/rpg.py` | NoneBot 指令处理器(薄),解析→调 service→回消息 |
| `bot/state.py` | 进程级单例:GameConfig、DB 连接、按玩家的 asyncio 锁 |
| `.env.example` | 沙箱机器人 AppID/Secret/Token 模板 |
| `README.md` | 运行与沙箱接入说明 |
| `tests/test_db.py` 等 | pytest |

`game_core/` 在本计划中**只读不改**(若发现引擎缺接口,作为 BLOCKED 上报,不要顺手改引擎)。

> 物品名称解析:`config.find_item_id(cfg, query)` —— 先按 `item_id` 精确匹配,再按中文 `name` 精确匹配,找不到抛 `ItemNotFound`。在 Task 2 里加到 `game_core/config.py`(纯函数,属于配置查询,允许加在这里;不引入新依赖)。

---

## Task 1: SQLite 连接与建表

**Files:**
- Create: `storage/__init__.py`(空)
- Create: `storage/db.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: 写失败测试 `tests/test_db.py`**

```python
from storage.db import get_conn, init_db


def test_init_db_creates_tables():
    conn = get_conn(":memory:")
    init_db(conn)
    names = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "players" in names
    assert "inventory" in names


def test_players_unique_group_user():
    conn = get_conn(":memory:")
    init_db(conn)
    conn.execute("INSERT INTO players (group_id,user_id,name,stamina_at,current_hp,created_at,last_active_at) "
                 "VALUES ('g','u','勇者',0,100,0,0)")
    import sqlite3
    import pytest
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO players (group_id,user_id,name,stamina_at,current_hp,created_at,last_active_at) "
                     "VALUES ('g','u','另一个',0,100,0,0)")


def test_row_factory_returns_mapping():
    conn = get_conn(":memory:")
    init_db(conn)
    row = conn.execute("SELECT 1 AS x").fetchone()
    assert row["x"] == 1
```

- [ ] **Step 2: 运行,确认失败**

Run: `pytest tests/test_db.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'storage'`

- [ ] **Step 3: 写实现 `storage/db.py`**

```python
from __future__ import annotations
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id        TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    name            TEXT NOT NULL,
    level           INTEGER NOT NULL DEFAULT 1,
    exp             INTEGER NOT NULL DEFAULT 0,
    gold            INTEGER NOT NULL DEFAULT 0,
    stamina         INTEGER NOT NULL DEFAULT 0,
    stamina_at      INTEGER NOT NULL,
    current_hp      INTEGER NOT NULL,
    current_depth   INTEGER NOT NULL DEFAULT 1,
    max_depth       INTEGER NOT NULL DEFAULT 1,
    created_at      INTEGER NOT NULL,
    last_active_at  INTEGER NOT NULL,
    UNIQUE(group_id, user_id)
);

CREATE TABLE IF NOT EXISTS inventory (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id   INTEGER NOT NULL REFERENCES players(id),
    item_id     TEXT NOT NULL,
    quantity    INTEGER NOT NULL DEFAULT 1,
    equipped    INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_inventory_player ON inventory(player_id);
CREATE INDEX IF NOT EXISTS idx_players_group ON players(group_id);
"""


def get_conn(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
```

- [ ] **Step 4: 运行,确认通过**

Run: `pytest tests/test_db.py -v`
Expected: PASS(3 passed)

- [ ] **Step 5: Commit**

```bash
git add storage/__init__.py storage/db.py tests/test_db.py
git commit -m "feat: SQLite 连接与建表"
```

---

## Task 2: 物品名称解析(config 辅助)

**Files:**
- Modify: `game_core/config.py`(在文件末尾追加一个纯函数,不改动既有内容)
- Test: `tests/test_find_item.py`

- [ ] **Step 1: 写失败测试 `tests/test_find_item.py`**

```python
import pytest
from pathlib import Path
from game_core.config import load_config, find_item_id
from game_core.errors import ItemNotFound

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CFG = load_config(DATA_DIR)


def test_find_by_id():
    assert find_item_id(CFG, "hp_potion") == "hp_potion"


def test_find_by_chinese_name():
    assert find_item_id(CFG, "治疗药水") == "hp_potion"


def test_find_unknown_raises():
    with pytest.raises(ItemNotFound):
        find_item_id(CFG, "屠龙刀")
```

- [ ] **Step 2: 运行,确认失败**

Run: `pytest tests/test_find_item.py -v`
Expected: FAIL,`ImportError: cannot import name 'find_item_id'`

- [ ] **Step 3: 在 `game_core/config.py` 末尾追加**

```python


def find_item_id(cfg: GameConfig, query: str) -> str:
    """按 item_id 或中文名解析出 item_id;找不到抛 ItemNotFound。"""
    from game_core.errors import ItemNotFound
    query = query.strip()
    if query in cfg.items:
        return query
    for it in cfg.items.values():
        if it.name == query:
            return it.id
    raise ItemNotFound(f"没有这件物品: {query}")
```

- [ ] **Step 4: 运行,确认通过**

Run: `pytest tests/test_find_item.py -v`
Expected: PASS(3 passed)

- [ ] **Step 5: Commit**

```bash
git add game_core/config.py tests/test_find_item.py
git commit -m "feat: 物品名称/ID 解析辅助"
```

---

## Task 3: 仓储层(Player 读写与群查询)

**Files:**
- Create: `storage/repository.py`
- Test: `tests/test_repository.py`

- [ ] **Step 1: 写失败测试 `tests/test_repository.py`**

```python
from storage.db import get_conn, init_db
from storage.repository import (
    get_player, create_player, save_player, list_group_players,
)
from game_core.models import Player, InventoryItem


def _conn():
    conn = get_conn(":memory:")
    init_db(conn)
    return conn


def _player(group="g", user="u", name="勇者"):
    return Player(group_id=group, user_id=user, name=name,
                  stamina_at=0, current_hp=100, created_at=0, last_active_at=0)


def test_create_assigns_id_and_roundtrips():
    conn = _conn()
    p = create_player(conn, _player())
    assert p.id is not None
    loaded = get_player(conn, "g", "u")
    assert loaded is not None
    assert loaded.name == "勇者"
    assert loaded.current_hp == 100


def test_get_missing_returns_none():
    conn = _conn()
    assert get_player(conn, "g", "nobody") is None


def test_save_persists_changes_and_inventory():
    conn = _conn()
    p = create_player(conn, _player())
    p.level = 5
    p.gold = 123
    p.inventory.append(InventoryItem(item_id="rusty_sword", quantity=1, equipped=True))
    p.inventory.append(InventoryItem(item_id="hp_potion", quantity=3, equipped=False))
    save_player(conn, p)

    loaded = get_player(conn, "g", "u")
    assert loaded.level == 5
    assert loaded.gold == 123
    inv = {i.item_id: i for i in loaded.inventory}
    assert inv["rusty_sword"].equipped is True
    assert inv["hp_potion"].quantity == 3


def test_save_inventory_no_duplicates_on_resave():
    conn = _conn()
    p = create_player(conn, _player())
    p.inventory.append(InventoryItem(item_id="hp_potion", quantity=1))
    save_player(conn, p)
    save_player(conn, p)          # 再存一次不应翻倍
    loaded = get_player(conn, "g", "u")
    pots = [i for i in loaded.inventory if i.item_id == "hp_potion"]
    assert len(pots) == 1


def test_list_group_players_is_group_scoped():
    conn = _conn()
    create_player(conn, _player(group="g1", user="a", name="A"))
    create_player(conn, _player(group="g1", user="b", name="B"))
    create_player(conn, _player(group="g2", user="c", name="C"))
    g1 = list_group_players(conn, "g1")
    assert {p.name for p in g1} == {"A", "B"}
```

- [ ] **Step 2: 运行,确认失败**

Run: `pytest tests/test_repository.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'storage.repository'`

- [ ] **Step 3: 写实现 `storage/repository.py`**

```python
from __future__ import annotations
import sqlite3
from game_core.models import Player, InventoryItem

PLAYER_COLS = [
    "group_id", "user_id", "name", "level", "exp", "gold", "stamina",
    "stamina_at", "current_hp", "current_depth", "max_depth",
    "created_at", "last_active_at",
]


def _row_to_player(row: sqlite3.Row, inv_rows: list[sqlite3.Row]) -> Player:
    p = Player(
        group_id=row["group_id"], user_id=row["user_id"], name=row["name"],
        level=row["level"], exp=row["exp"], gold=row["gold"],
        stamina=row["stamina"], stamina_at=row["stamina_at"],
        current_hp=row["current_hp"], current_depth=row["current_depth"],
        max_depth=row["max_depth"], created_at=row["created_at"],
        last_active_at=row["last_active_at"], id=row["id"],
    )
    p.inventory = [
        InventoryItem(item_id=r["item_id"], quantity=r["quantity"],
                      equipped=bool(r["equipped"]))
        for r in inv_rows
    ]
    return p


def _load_inventory(conn: sqlite3.Connection, player_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM inventory WHERE player_id=?", (player_id,)).fetchall()


def get_player(conn: sqlite3.Connection, group_id: str, user_id: str) -> Player | None:
    row = conn.execute(
        "SELECT * FROM players WHERE group_id=? AND user_id=?",
        (group_id, user_id)).fetchone()
    if row is None:
        return None
    return _row_to_player(row, _load_inventory(conn, row["id"]))


def create_player(conn: sqlite3.Connection, player: Player) -> Player:
    placeholders = ",".join("?" * len(PLAYER_COLS))
    cur = conn.execute(
        f"INSERT INTO players ({','.join(PLAYER_COLS)}) VALUES ({placeholders})",
        tuple(getattr(player, c) for c in PLAYER_COLS))
    player.id = cur.lastrowid
    _save_inventory(conn, player)
    conn.commit()
    return player


def save_player(conn: sqlite3.Connection, player: Player) -> None:
    set_clause = ",".join(f"{c}=?" for c in PLAYER_COLS)
    conn.execute(
        f"UPDATE players SET {set_clause} WHERE id=?",
        (*[getattr(player, c) for c in PLAYER_COLS], player.id))
    _save_inventory(conn, player)
    conn.commit()


def _save_inventory(conn: sqlite3.Connection, player: Player) -> None:
    # 背包条目很少,采用"删旧插新"保证与内存状态一致
    conn.execute("DELETE FROM inventory WHERE player_id=?", (player.id,))
    for it in player.inventory:
        conn.execute(
            "INSERT INTO inventory (player_id,item_id,quantity,equipped) "
            "VALUES (?,?,?,?)",
            (player.id, it.item_id, it.quantity, int(it.equipped)))


def list_group_players(conn: sqlite3.Connection, group_id: str) -> list[Player]:
    rows = conn.execute(
        "SELECT * FROM players WHERE group_id=?", (group_id,)).fetchall()
    return [_row_to_player(r, _load_inventory(conn, r["id"])) for r in rows]
```

- [ ] **Step 4: 运行,确认通过**

Run: `pytest tests/test_repository.py -v`
Expected: PASS(5 passed)

- [ ] **Step 5: Commit**

```bash
git add storage/repository.py tests/test_repository.py
git commit -m "feat: 仓储层(Player 读写/背包同步/群查询)"
```

---

## Task 4: 服务层 —— 注册与状态

**Files:**
- Create: `app/__init__.py`(空)
- Create: `app/services.py`
- Test: `tests/test_services_register.py`

- [ ] **Step 1: 写失败测试 `tests/test_services_register.py`**

```python
import pytest
from pathlib import Path
from storage.db import get_conn, init_db
from game_core.config import load_config
from game_core.stats import hp_max
from game_core.errors import DuplicateName, CharacterNotFound
from app.services import register, status

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CFG = load_config(DATA_DIR)


def _conn():
    conn = get_conn(":memory:")
    init_db(conn)
    return conn


def test_register_creates_full_hp_character():
    conn = _conn()
    p = register(conn, CFG, "g", "u", "小明", now=1000)
    assert p.id is not None
    assert p.name == "小明"
    assert p.current_hp == hp_max(p, CFG)
    assert p.stamina_at == 1000


def test_register_duplicate_name_in_group_rejected():
    conn = _conn()
    register(conn, CFG, "g", "u1", "小明", now=0)
    with pytest.raises(DuplicateName):
        register(conn, CFG, "g", "u2", "小明", now=0)


def test_same_user_cannot_register_twice():
    conn = _conn()
    register(conn, CFG, "g", "u1", "小明", now=0)
    with pytest.raises(DuplicateName):
        register(conn, CFG, "g", "u1", "小红", now=0)


def test_status_settles_stamina_and_persists():
    conn = _conn()
    register(conn, CFG, "g", "u", "小明", now=0)
    # 过 60 分钟后查状态,应已结算出体力(每5分钟+1 → 12)
    p = status(conn, CFG, "g", "u", now=60 * 60)
    assert p.stamina == 12
    # 再查一次(同一时刻)不应继续增长
    p2 = status(conn, CFG, "g", "u", now=60 * 60)
    assert p2.stamina == 12


def test_status_missing_character_raises():
    conn = _conn()
    with pytest.raises(CharacterNotFound):
        status(conn, CFG, "g", "nobody", now=0)
```

- [ ] **Step 2: 运行,确认失败**

Run: `pytest tests/test_services_register.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'app'`

- [ ] **Step 3: 写实现 `app/services.py`**

```python
from __future__ import annotations
import sqlite3
from game_core.models import Player, make_new_player, GameConfig
from game_core.stats import hp_max
from game_core.stamina import settle_stamina
from game_core.errors import DuplicateName, CharacterNotFound, GameError
from storage import repository as repo


def _require(conn: sqlite3.Connection, cfg: GameConfig,
             group_id: str, user_id: str) -> Player:
    p = repo.get_player(conn, group_id, user_id)
    if p is None:
        raise CharacterNotFound("你在本群还没有角色,先发「注册 角色名」吧~")
    return p


def register(conn: sqlite3.Connection, cfg: GameConfig,
             group_id: str, user_id: str, name: str, now: int) -> Player:
    name = name.strip()
    if not name or len(name) > 12:
        raise GameError("角色名需为 1-12 个字符")
    if repo.get_player(conn, group_id, user_id) is not None:
        raise DuplicateName("你在本群已经有角色啦")
    for other in repo.list_group_players(conn, group_id):
        if other.name == name:
            raise DuplicateName(f"本群已有人叫「{name}」,换一个吧")
    # 用 1 级 hp_max 初始化满血
    probe = Player(group_id=group_id, user_id=user_id, name=name)
    start_hp = hp_max(probe, cfg)
    player = make_new_player(group_id, user_id, name, now=now, start_hp=start_hp)
    return repo.create_player(conn, player)


def status(conn: sqlite3.Connection, cfg: GameConfig,
           group_id: str, user_id: str, now: int) -> Player:
    p = _require(conn, cfg, group_id, user_id)
    settle_stamina(p, now, cfg.balance.stamina_regen_minutes, cfg.balance.stamina_max)
    p.last_active_at = now
    repo.save_player(conn, p)
    return p
```

- [ ] **Step 4: 运行,确认通过**

Run: `pytest tests/test_services_register.py -v`
Expected: PASS(5 passed)

- [ ] **Step 5: Commit**

```bash
git add app/__init__.py app/services.py tests/test_services_register.py
git commit -m "feat: 服务层注册与状态(含体力结算落库)"
```

---

## Task 5: 服务层 —— 探索 / 背包动作 / 商店 / 排行榜

**Files:**
- Modify: `app/services.py`(追加函数)
- Test: `tests/test_services_actions.py`

- [ ] **Step 1: 写失败测试 `tests/test_services_actions.py`**

```python
import random
import pytest
from pathlib import Path
from storage.db import get_conn, init_db
from storage import repository as repo
from game_core.config import load_config
from game_core.models import InventoryItem
from game_core.errors import NotEnoughGold, ItemNotFound, CharacterNotFound
from app.services import (
    register, do_explore, do_equip, do_use, do_buy, get_ranking,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CFG = load_config(DATA_DIR)


def _conn():
    conn = get_conn(":memory:")
    init_db(conn)
    return conn


def test_do_explore_persists_progress():
    conn = _conn()
    register(conn, CFG, "g", "u", "小明", now=0)
    res = do_explore(conn, CFG, "g", "u", now=60 * 60, rng=random.Random(1))
    assert len(res.steps) >= 1
    # 重新读档:体力应已被消耗并落库
    reloaded = repo.get_player(conn, "g", "u")
    assert reloaded.stamina == res.stamina_left


def test_do_explore_requires_character():
    conn = _conn()
    with pytest.raises(CharacterNotFound):
        do_explore(conn, CFG, "g", "nobody", now=0, rng=random.Random(1))


def test_do_buy_and_equip_persist():
    conn = _conn()
    register(conn, CFG, "g", "u", "小明", now=0)
    p = repo.get_player(conn, "g", "u")
    p.gold = 100
    repo.save_player(conn, p)

    do_buy(conn, CFG, "g", "u", "生锈的铁剑")     # 中文名购买,价 50
    after_buy = repo.get_player(conn, "g", "u")
    assert after_buy.gold == 50
    assert any(i.item_id == "rusty_sword" for i in after_buy.inventory)

    do_equip(conn, CFG, "g", "u", "生锈的铁剑")
    after_equip = repo.get_player(conn, "g", "u")
    assert any(i.item_id == "rusty_sword" and i.equipped for i in after_equip.inventory)


def test_do_buy_insufficient_gold():
    conn = _conn()
    register(conn, CFG, "g", "u", "小明", now=0)   # 0 金币
    with pytest.raises(NotEnoughGold):
        do_buy(conn, CFG, "g", "u", "精铁长剑")    # 价 200


def test_do_use_potion():
    conn = _conn()
    register(conn, CFG, "g", "u", "小明", now=0)
    p = repo.get_player(conn, "g", "u")
    p.current_hp = 10
    p.inventory.append(InventoryItem(item_id="hp_potion", quantity=1))
    repo.save_player(conn, p)
    do_use(conn, CFG, "g", "u", "治疗药水")
    after = repo.get_player(conn, "g", "u")
    assert after.current_hp == 60                 # 10 + 50
    assert all(i.item_id != "hp_potion" for i in after.inventory)


def test_get_ranking_group_scoped_and_sorted():
    conn = _conn()
    for u, name, lvl in [("a", "A", 3), ("b", "B", 7), ("c", "C", 5)]:
        register(conn, CFG, "g1", u, name, now=0)
        p = repo.get_player(conn, "g1", u); p.level = lvl; repo.save_player(conn, p)
    register(conn, CFG, "g2", "z", "Z", now=0)    # 别的群,不应出现
    ranked = get_ranking(conn, CFG, "g1", key="level")
    assert [p.name for p in ranked] == ["B", "C", "A"]
```

- [ ] **Step 2: 运行,确认失败**

Run: `pytest tests/test_services_actions.py -v`
Expected: FAIL,`ImportError: cannot import name 'do_explore'`

- [ ] **Step 3: 在 `app/services.py` 追加**

```python
import random as _random
from game_core.config import find_item_id
from game_core.exploration import explore as _explore
from game_core import loot as _loot, shop as _shop, ranking as _ranking
from game_core.models import ExploreResult, ItemDef


def do_explore(conn, cfg, group_id, user_id, now, rng) -> ExploreResult:
    p = _require(conn, cfg, group_id, user_id)
    res = _explore(p, cfg, now, rng)
    repo.save_player(conn, p)
    return res


def do_equip(conn, cfg, group_id, user_id, item_query) -> Player:
    p = _require(conn, cfg, group_id, user_id)
    _loot.equip(p, find_item_id(cfg, item_query), cfg)
    repo.save_player(conn, p)
    return p


def do_unequip(conn, cfg, group_id, user_id, item_query) -> Player:
    p = _require(conn, cfg, group_id, user_id)
    _loot.unequip(p, find_item_id(cfg, item_query), cfg)
    repo.save_player(conn, p)
    return p


def do_use(conn, cfg, group_id, user_id, item_query) -> Player:
    p = _require(conn, cfg, group_id, user_id)
    _loot.use_item(p, find_item_id(cfg, item_query), cfg)
    repo.save_player(conn, p)
    return p


def do_buy(conn, cfg, group_id, user_id, item_query) -> Player:
    p = _require(conn, cfg, group_id, user_id)
    _shop.buy(p, find_item_id(cfg, item_query), cfg)
    repo.save_player(conn, p)
    return p


def shop_list(cfg) -> list[ItemDef]:
    return _shop.list_shop(cfg)


def get_ranking(conn, cfg, group_id, key="level", limit=10) -> list[Player]:
    players = repo.list_group_players(conn, group_id)
    return _ranking.rank_players(players, key=key, limit=limit)
```

- [ ] **Step 4: 运行,确认通过**

Run: `pytest tests/test_services_actions.py -v`
Expected: PASS(6 passed)

- [ ] **Step 5: Commit**

```bash
git add app/services.py tests/test_services_actions.py
git commit -m "feat: 服务层探索/装备/使用/购买/排行榜"
```

---

## Task 6: 中文消息格式化

**Files:**
- Create: `bot/__init__.py`(空,本任务仅占位;NoneBot 初始化在 Task 8)
- Create: `bot/formatting.py`
- Test: `tests/test_formatting.py`

> 注:为避免本任务引入 NoneBot 依赖,`bot/__init__.py` 保持为空文件,不在其中 import nonebot。

- [ ] **Step 1: 写失败测试 `tests/test_formatting.py`**

```python
from pathlib import Path
from game_core.config import load_config
from game_core.models import Player, InventoryItem, ExploreResult, StepLog
from game_core.stats import hp_max
from bot.formatting import (
    render_explore, render_status, render_ranking, render_shop, render_inventory,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CFG = load_config(DATA_DIR)


def _player():
    p = Player(group_id="g", user_id="u", name="小明", level=4, gold=312,
               stamina=12, current_depth=6, max_depth=6)
    p.current_hp = 73
    return p


def test_render_explore_contains_key_facts():
    res = ExploreResult(
        steps=[StepLog(kind="combat", depth=4, monster="史莱姆", won=True,
                       rounds=2, gold=6, exp=15, hp_after=88),
               StepLog(kind="treasure", depth=5, gold=24, hp_after=88)],
        total_gold=30, total_exp=15, items_gained=["rusty_sword"],
        level_ups=1, defeated=False, stamina_left=0,
        depth_before=3, depth_after=6, hp_after=88, hp_max=120)
    text = render_explore(_player(), res, CFG)
    assert "史莱姆" in text
    assert "30" in text          # 总金币
    assert "第6层" in text or "6" in text
    assert "升级" in text         # level_ups>0


def test_render_explore_defeat_message():
    res = ExploreResult(steps=[StepLog(kind="combat", depth=6, monster="哥布林",
                                        won=False, rounds=3, hp_after=0)],
                        total_gold=0, total_exp=0, items_gained=[], level_ups=0,
                        defeated=True, stamina_left=20, depth_before=6,
                        depth_after=1, hp_after=100, hp_max=100)
    text = render_explore(_player(), res, CFG)
    assert "回城" in text or "重伤" in text


def test_render_status_contains_stats():
    text = render_status(_player(), CFG)
    assert "小明" in text
    assert "Lv.4" in text or "4" in text
    assert "312" in text         # 金币


def test_render_ranking_lists_names_with_rank():
    players = [_player()]
    text = render_ranking(players, CFG, key="level")
    assert "小明" in text
    assert "🥇" in text           # 第一名奖牌
    assert "等级榜" in text


def test_render_shop_lists_priced_items():
    text = render_shop(CFG)
    assert "治疗药水" in text
    assert "20" in text          # 价格


def test_render_inventory_lists_items_and_equipped():
    p = _player()
    p.inventory = [InventoryItem(item_id="rusty_sword", quantity=1, equipped=True),
                   InventoryItem(item_id="hp_potion", quantity=3, equipped=False)]
    text = render_inventory(p, CFG)
    assert "生锈的铁剑" in text
    assert "已装备" in text
    assert "治疗药水" in text
    assert "3" in text           # 数量


def test_render_inventory_empty():
    p = _player()
    p.inventory = []
    assert "空" in render_inventory(p, CFG)
```

- [ ] **Step 2: 运行,确认失败**

Run: `pytest tests/test_formatting.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'bot.formatting'`(或 `bot`)

- [ ] **Step 3: 写实现 `bot/formatting.py`**

```python
from __future__ import annotations
from game_core.models import Player, ExploreResult, GameConfig
from game_core.stats import hp_max, attack, defense, power


def _item_name(cfg: GameConfig, item_id: str) -> str:
    it = cfg.items.get(item_id)
    return it.name if it else item_id


def render_explore(player: Player, res: ExploreResult, cfg: GameConfig) -> str:
    lines = [f"🗡️ 【{player.name}】的下潜 (第{res.depth_before}层 → 第{res.depth_after}层)", ""]
    for s in res.steps:
        if s.kind == "combat" and s.won:
            extra = f"  ✨ 掉落【{'、'.join(_item_name(cfg, i) for i in s.items)}】" if s.items else ""
            lines.append(f"第{s.depth}层 ⚔️ {s.monster} → {s.rounds}回合击败  +{s.exp}exp +{s.gold}金币{extra}")
        elif s.kind == "combat" and not s.won:
            lines.append(f"第{s.depth}层 ⚔️ 不敌{s.monster},重伤回城…")
        elif s.kind == "treasure":
            lines.append(f"第{s.depth}层 📦 发现宝箱  +{s.gold}金币")
        elif s.kind == "trap":
            lines.append(f"第{s.depth}层 ⚠️ {s.text or '踩中陷阱'}")
        else:  # flavor
            lines.append(f"第{s.depth}层 🚶 {s.text}")
    lines.append("──────────────")
    got = f"  获得{len(res.items_gained)}件物品" if res.items_gained else ""
    lines.append(f"本次合计:+{res.total_exp}exp  +{res.total_gold}金币{got}")
    lines.append(f"❤️ HP {res.hp_after}/{res.hp_max}   ⚡ 体力 {res.stamina_left}")
    if res.level_ups > 0:
        lines.append(f"📊 升级 +{res.level_ups}!  当前 Lv.{player.level}")
    lines.append(f"🏆 最深抵达 第{player.max_depth}层")
    if res.defeated:
        lines.append("💀 重伤回城,已回到第 1 层(金币略有损失)")
    elif res.stamina_left < cfg.balance.stamina_cost_per_step:
        lines.append("💤 体力耗尽,攒一攒再来下潜~")
    return "\n".join(lines)


def render_status(player: Player, cfg: GameConfig) -> str:
    return "\n".join([
        f"🛡️ {player.name}  Lv.{player.level}  (本群)",
        f"经验 {player.exp}",
        f"❤️ HP {player.current_hp}/{hp_max(player, cfg)}   ⚡ 体力 {player.stamina}/{cfg.balance.stamina_max}",
        f"⚔️ 攻击 {attack(player, cfg)}   🛡️ 防御 {defense(player, cfg)}   💪 战力 {power(player, cfg)}",
        f"💰 金币 {player.gold}   🏆 最深 第{player.max_depth}层",
        "🎒 装备:" + ("、".join(_item_name(cfg, i.item_id) for i in player.inventory if i.equipped) or "无"),
    ])


def render_ranking(players, cfg: GameConfig, key: str = "level") -> str:
    title = "🏆 本群等级榜" if key == "level" else "🏆 本群深度榜"
    lines = [title]
    medals = ["🥇", "🥈", "🥉"]
    for i, p in enumerate(players):
        rank = medals[i] if i < 3 else f"{i + 1}."
        lines.append(f"{rank} {p.name}  Lv.{p.level}  最深第{p.max_depth}层")
    if len(lines) == 1:
        lines.append("还没有人上榜,快发「探索」吧~")
    return "\n".join(lines)


def render_shop(cfg: GameConfig) -> str:
    from game_core.shop import list_shop
    lines = ["🏪 商店(发「购买 物品名」)"]
    for it in list_shop(cfg):
        lines.append(f"・{it.name}  {it.price}金币")
    return "\n".join(lines)


def render_inventory(player: Player, cfg: GameConfig) -> str:
    if not player.inventory:
        return "🎒 背包空空如也,发「探索」去找点东西吧~"
    lines = ["🎒 背包"]
    for it in player.inventory:
        tag = "(已装备)" if it.equipped else ""
        lines.append(f"・{_item_name(cfg, it.item_id)} ×{it.quantity}{tag}")
    return "\n".join(lines)
```

- [ ] **Step 4: 运行,确认通过**

Run: `pytest tests/test_formatting.py -v`
Expected: PASS(7 passed)

- [ ] **Step 5: Commit**

```bash
git add bot/__init__.py bot/formatting.py tests/test_formatting.py
git commit -m "feat: 中文消息格式化(探索/状态/排行/商店)"
```

---

## Task 7: 全量回归 + 服务层冒烟

**Files:**
- Test: `tests/test_services_smoke.py`

- [ ] **Step 1: 写测试 `tests/test_services_smoke.py`**

```python
import random
from pathlib import Path
from storage.db import get_conn, init_db
from storage import repository as repo
from game_core.config import load_config
from app.services import register, do_explore, get_ranking
from bot.formatting import render_explore, render_status, render_ranking

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CFG = load_config(DATA_DIR)


def test_two_players_full_flow_with_persistence():
    conn = get_conn(":memory:")
    init_db(conn)
    rng = random.Random(7)
    register(conn, CFG, "g", "u1", "小明", now=0)
    register(conn, CFG, "g", "u2", "小红", now=0)

    # 各挂机 3 小时各探索一次,落库
    for u in ("u1", "u2"):
        res = do_explore(conn, CFG, "g", u, now=3 * 3600, rng=rng)
        text = render_explore(repo.get_player(conn, "g", u), res, CFG)
        assert "下潜" in text

    ranked = get_ranking(conn, CFG, "g", key="level")
    assert len(ranked) == 2
    assert "本群" in render_ranking(ranked, CFG, key="level")
    assert "小明" in render_status(repo.get_player(conn, "g", "u1"), CFG)
```

- [ ] **Step 2: 运行,确认通过**

Run: `pytest tests/test_services_smoke.py -v`
Expected: PASS(1 passed)

- [ ] **Step 3: 全量回归**

Run: `python -m pytest -q`
Expected: 全绿(计划一 53 项 + 计划二新增,约 75+ 项)。

- [ ] **Step 4: Commit**

```bash
git add tests/test_services_smoke.py
git commit -m "test: 服务层+格式化端到端冒烟(双玩家落库)"
```

---

## Task 8: NoneBot2 接入(集成 + 沙箱验收)

> ⚠️ **本任务是框架集成,不是纯逻辑**:NoneBot2 / nonebot-adapter-qq 的事件类名与发送 API 随版本变化。下面给出标准骨架,**实现时务必对照已安装版本的官方文档**(https://github.com/nonebot/adapter-qq 与 https://nonebot.dev)核对群消息事件类(常见为 `GroupAtMessageCreateEvent`)与 `Bot.send` 用法。本任务的**真正验收是沙箱频道/群里人工跑通**,而非单元测试。

**Files:**
- Modify: `pyproject.toml`(加 nonebot2、nonebot-adapter-qq 依赖)
- Create: `bot/state.py`(进程级 GameConfig + DB 连接 + 玩家锁)
- Create: `bot/plugins/rpg.py`(指令处理器)
- Create: `bot/__main__.py` 或 `bot.py`(NoneBot 启动入口 + 适配器注册)
- Create: `.env.example`
- Create: `README.md`

- [ ] **Step 1: 加依赖到 `pyproject.toml`**

在 `dependencies` 增加(版本以安装时最新稳定版为准):
```toml
dependencies = [
    "pyyaml>=6.0",
    "nonebot2[fastapi]>=2.3",
    "nonebot-adapter-qq>=1.5",
]
```
然后 `pip install -e ".[dev]"`,确认 `import nonebot` 成功。

- [ ] **Step 2: 写 `bot/state.py`(进程级单例 + 玩家锁)**

```python
from __future__ import annotations
import asyncio
import time
from collections import defaultdict
from pathlib import Path
from game_core.config import load_config
from storage.db import get_conn, init_db

_BASE = Path(__file__).resolve().parent.parent
CFG = load_config(_BASE / "data")

_conn = get_conn(str(_BASE / "rpg.db"))
init_db(_conn)


def conn():
    return _conn


_locks: dict[tuple[str, str], asyncio.Lock] = defaultdict(asyncio.Lock)


def player_lock(group_id: str, user_id: str) -> asyncio.Lock:
    return _locks[(group_id, user_id)]


def now() -> int:
    return int(time.time())
```

- [ ] **Step 3: 写 `bot/plugins/rpg.py`(指令处理器骨架)**

> 下面用 NoneBot2 通用 API 表达意图;`GroupAtMessageCreateEvent` 的导入与 `group_openid`/`author` 字段名以 adapter-qq 实际版本为准。每个处理器统一:取 group_id/user_id → 加玩家锁 → 调 service → 格式化回复 → 捕获 `GameError` 友好提示、捕获未知异常记日志不外泄。

```python
import random
from nonebot import on_command
from nonebot.rule import to_me
from nonebot.log import logger
from nonebot.adapters.qq import GroupAtMessageCreateEvent  # 以实际版本为准
from nonebot.adapters.qq import Bot

from game_core.errors import GameError
from bot import state
from bot import formatting as fmt
from app import services


def _ids(event: GroupAtMessageCreateEvent):
    # 字段名以 adapter-qq 实际版本为准
    return event.group_openid, event.author.member_openid


async def _guard(bot, event, coro_factory):
    gid, uid = _ids(event)
    async with state.player_lock(gid, uid):
        try:
            return await coro_factory(gid, uid)
        except GameError as e:
            await bot.send(event, str(e))
        except Exception:
            logger.exception("RPG 指令处理异常")
            await bot.send(event, "⚠️ 出了点小问题,已记录,稍后再试~")
    return None


register_cmd = on_command("注册", aliases={"创建"}, rule=to_me())

@register_cmd.handle()
async def _(bot: Bot, event: GroupAtMessageCreateEvent):
    name = event.get_plaintext().replace("注册", "").replace("创建", "").strip()
    async def do(gid, uid):
        services.register(state.conn(), state.CFG, gid, uid, name, state.now())
        await bot.send(event, f"🎉 角色「{name}」创建成功!发「探索」开始冒险~")
    await _guard(bot, event, do)


explore_cmd = on_command("探索", aliases={"下潜", "冒险"}, rule=to_me())

@explore_cmd.handle()
async def _(bot: Bot, event: GroupAtMessageCreateEvent):
    async def do(gid, uid):
        from storage import repository as repo
        res = services.do_explore(state.conn(), state.CFG, gid, uid,
                                  state.now(), random.Random())
        player = repo.get_player(state.conn(), gid, uid)
        await bot.send(event, fmt.render_explore(player, res, state.CFG))
    await _guard(bot, event, do)


status_cmd = on_command("状态", aliases={"我", "角色"}, rule=to_me())

@status_cmd.handle()
async def _(bot: Bot, event: GroupAtMessageCreateEvent):
    async def do(gid, uid):
        p = services.status(state.conn(), state.CFG, gid, uid, state.now())
        await bot.send(event, fmt.render_status(p, state.CFG))
    await _guard(bot, event, do)


# 同理实现:背包/装备/卸下/使用/商店/购买/排行榜/帮助
# 装备示例:
equip_cmd = on_command("装备", rule=to_me())

@equip_cmd.handle()
async def _(bot: Bot, event: GroupAtMessageCreateEvent):
    arg = event.get_plaintext().replace("装备", "").strip()
    async def do(gid, uid):
        services.do_equip(state.conn(), state.CFG, gid, uid, arg)
        await bot.send(event, f"已装备【{arg}】")
    await _guard(bot, event, do)
```

- [ ] **Step 4: 写启动入口 `bot/__main__.py`**

```python
import nonebot
from nonebot.adapters.qq import Adapter

nonebot.init()
driver = nonebot.get_driver()
driver.register_adapter(Adapter)

nonebot.load_plugin("bot.plugins.rpg")

if __name__ == "__main__":
    nonebot.run()
```

- [ ] **Step 5: 写 `.env.example`**

```dotenv
DRIVER=~fastapi
# 从 QQ 开放平台(q.qq.com)开发设置获取,复制本文件为 .env 后填入
QQ_BOTS='[{"id": "你的AppID", "token": "你的Token", "secret": "你的AppSecret"}]'
```

- [ ] **Step 6: 写 `README.md`**(运行 + 沙箱接入步骤)

至少包含:安装 `pip install -e ".[dev]"`、复制 `.env.example` 为 `.env` 填入沙箱机器人三要素、`python -m bot` 启动、在 QQ 开放平台沙箱频道/群 @机器人发「注册 名字」「探索」验收。

- [ ] **Step 7: 全量回归(确保接入未破坏纯逻辑测试)**

Run: `python -m pytest -q`
Expected: 全绿(纯逻辑测试不依赖 NoneBot,应不受影响)。

- [ ] **Step 8: 人工沙箱验收(必须)**

在 QQ 开放平台沙箱里 @机器人依次验证:`注册 测试侠` → `探索`(等待或多次)→ `状态` → `商店` → `购买 治疗药水` → `排行榜`。确认回复正常、异常不外泄。

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml bot/state.py bot/plugins/rpg.py bot/__main__.py .env.example README.md
git commit -m "feat: NoneBot2 + QQ 适配器接入(沙箱可跑)"
```

---

## 完成标准

- [ ] `pytest` 全绿(计划一 + 计划二的存储/服务/格式化测试)。
- [ ] 在 QQ 开放平台**沙箱**里能 @机器人完成:注册 → 探索(挂机攒体力一次结算)→ 状态 → 商店 → 购买 → 装备 → 排行榜 全流程。
- [ ] 异常不外泄到群(GameError 友好提示;未知异常记日志 + 通用提示)。
- [ ] 存档持久化:重启机器人后角色与进度仍在(SQLite 文件 `rpg.db`)。

---

## 非目标(留待 v2+)

- 真实大群上线 / 过审 / 云服务器常驻部署
- 战力榜、PvP/切磋、组队、交易行、公会
- 手写剧情主线、定时活动
- 多进程/分布式(单进程 + 单 SQLite 足够沙箱与小群)
