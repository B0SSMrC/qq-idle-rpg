# QQ 文字挂机探索 RPG —— 游戏引擎(game_core)实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现一个零 NoneBot 依赖、全程 TDD、测试全绿的纯 Python 游戏引擎 `game_core`,能在 REPL 里跑完整的角色生命周期(注册→挂机回体力→探索→战斗→升级→掉落→买装备→排行)。

**Architecture:** 分层架构的「核心层」。所有游戏逻辑都是「数据进 → 结果出」的纯函数/类,`now`(时间)和 `rng`(随机源)作为参数注入以保证可复现测试。配置来自只读 YAML,玩家状态用内存 `Player` 数据类表示(持久化是下一份计划的事)。

**Tech Stack:** Python 3.10+、PyYAML(配置)、pytest(测试)、dataclasses。

参考设计文档:`docs/specs/2026-06-18-qq-idle-rpg-design.md`

---

## 文件结构

| 文件 | 职责 |
|---|---|
| `pyproject.toml` | 依赖与 pytest 配置 |
| `data/balance.yaml` | 全局数值旋钮 |
| `data/monsters.yaml` | 怪物表 |
| `data/events.yaml` | 探索事件表 |
| `data/items.yaml` | 物品/装备/商品表 |
| `game_core/errors.py` | 领域异常 |
| `game_core/models.py` | 所有数据类:配置模型、Player、结果对象 |
| `game_core/config.py` | 加载 + 校验 YAML → `GameConfig` |
| `game_core/stats.py` | 派生属性:hp_max / atk / defense / power |
| `game_core/stamina.py` | 离线体力结算 |
| `game_core/combat.py` | 战斗数值结算 |
| `game_core/progression.py` | 经验曲线、升级、重伤回城 |
| `game_core/loot.py` | 掉落、背包堆叠、装备/卸下、使用消耗品 |
| `game_core/shop.py` | 商店列表与购买 |
| `game_core/ranking.py` | 排行榜排序(纯函数) |
| `game_core/exploration.py` | 探索循环(组合以上所有系统) |
| `tests/*` | 每个系统一一对应的 pytest |

**约定:** `def` 是 Python 关键字,故防御力字段统一命名 `defense`;YAML 中用 `def` 键,加载时映射到 `defense`。

---

## Task 1: 项目脚手架

**Files:**
- Create: `pyproject.toml`
- Create: `game_core/__init__.py`(空)
- Create: `tests/__init__.py`(空)
- Create: `data/`(目录,本任务先建空目录占位)

- [ ] **Step 1: 写 `pyproject.toml`**

```toml
[project]
name = "qq-idle-rpg"
version = "0.1.0"
description = "QQ 文字挂机探索 RPG 机器人"
requires-python = ">=3.10"
dependencies = [
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v"
```

- [ ] **Step 2: 建空包文件**

创建空文件 `game_core/__init__.py` 和 `tests/__init__.py`,并建立空目录 `data/`。

- [ ] **Step 3: 安装依赖并验证 pytest 可运行**

Run: `pip install -e ".[dev]"` 然后 `pytest`
Expected: pytest 启动,输出 `collected 0 items`(暂无测试)。

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml game_core/__init__.py tests/__init__.py
git commit -m "chore: 项目脚手架与 pytest 配置"
```

---

## Task 2: 种子配置 YAML

**Files:**
- Create: `data/balance.yaml`
- Create: `data/monsters.yaml`
- Create: `data/events.yaml`
- Create: `data/items.yaml`

本任务只写数据文件,无测试(下个任务的加载器会校验它们)。

- [ ] **Step 1: 写 `data/balance.yaml`**

```yaml
stamina:
  regen_minutes: 5      # 每 5 分钟回 1 点
  max: 50
  cost_per_step: 5      # 满体力可走 10 步
leveling:
  base_exp: 100         # 1→2 级所需经验
  growth: 1.4
stats_per_level:
  hp: 20
  atk: 3
  def: 2
base_stats:             # 1 级基础属性
  hp: 100
  atk: 10
  def: 5
defeat_penalty:
  gold_loss_pct: 0.1
```

- [ ] **Step 2: 写 `data/items.yaml`**

```yaml
- id: rusty_sword
  name: 生锈的铁剑
  slot: weapon
  atk: 5
  rarity: common
  price: 50
- id: iron_sword
  name: 精铁长剑
  slot: weapon
  atk: 12
  rarity: uncommon
  price: 200
- id: leather_armor
  name: 皮甲
  slot: armor
  def: 4
  hp: 20
  rarity: common
  price: 80
- id: hp_potion
  name: 治疗药水
  slot: consumable
  heal: 50
  price: 20
```

- [ ] **Step 3: 写 `data/monsters.yaml`**

> 注意:出现层数范围用 `depth` 键,防御力用 `def` 键,两者不要混淆。

```yaml
- id: slime
  name: 史莱姆
  depth: [1, 5]
  hp: 30
  atk: 5
  def: 1
  exp: 15
  gold: [3, 8]
  drops:
    - { item: rusty_sword, chance: 0.05 }
- id: goblin
  name: 哥布林
  depth: [3, 10]
  hp: 60
  atk: 12
  def: 3
  exp: 30
  gold: [8, 18]
  drops:
    - { item: leather_armor, chance: 0.04 }
    - { item: hp_potion, chance: 0.10 }
- id: skeleton
  name: 骷髅战士
  depth: [8, 20]
  hp: 120
  atk: 22
  def: 8
  exp: 60
  gold: [15, 35]
  drops:
    - { item: iron_sword, chance: 0.03 }
```

- [ ] **Step 4: 写 `data/events.yaml`**

```yaml
- id: combat
  type: combat
  weight: 60
- id: treasure
  type: treasure
  weight: 20
  reward_gold: [10, 30]
- id: trap
  type: trap
  weight: 10
  damage_pct: 0.1
- id: flavor
  type: flavor
  weight: 10
  texts:
    - "走廊空荡荡的,只有水滴回声。"
    - "墙上的火把忽明忽暗。"
    - "你听见远处有什么东西在爬动。"
```

- [ ] **Step 5: Commit**

```bash
git add data/
git commit -m "feat: 种子配置(数值/怪物/事件/物品)"
```

---

## Task 3: 领域异常

**Files:**
- Create: `game_core/errors.py`
- Test: `tests/test_errors.py`

- [ ] **Step 1: 写失败测试 `tests/test_errors.py`**

```python
from game_core.errors import (
    GameError, NotEnoughStamina, CharacterNotFound,
    DuplicateName, ItemNotFound, NotEnoughGold, InvalidSlot,
)


def test_domain_errors_are_gameerror_subclasses():
    for cls in (NotEnoughStamina, CharacterNotFound, DuplicateName,
                ItemNotFound, NotEnoughGold, InvalidSlot):
        assert issubclass(cls, GameError)


def test_error_carries_message():
    err = NotEnoughStamina("体力不够")
    assert str(err) == "体力不够"
    assert isinstance(err, GameError)
```

- [ ] **Step 2: 运行,确认失败**

Run: `pytest tests/test_errors.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'game_core.errors'`

- [ ] **Step 3: 写实现 `game_core/errors.py`**

```python
class GameError(Exception):
    """所有可向玩家友好展示的业务错误的基类。"""


class NotEnoughStamina(GameError):
    """体力不足以执行该操作。"""


class CharacterNotFound(GameError):
    """该玩家在本群尚无角色。"""


class DuplicateName(GameError):
    """同群内角色名重复。"""


class ItemNotFound(GameError):
    """物品在配置或背包中不存在。"""


class NotEnoughGold(GameError):
    """金币不足。"""


class InvalidSlot(GameError):
    """装备槽位不匹配(例如把消耗品当武器装备)。"""
```

- [ ] **Step 4: 运行,确认通过**

Run: `pytest tests/test_errors.py -v`
Expected: PASS(2 passed)

- [ ] **Step 5: Commit**

```bash
git add game_core/errors.py tests/test_errors.py
git commit -m "feat: 领域异常定义"
```

---

## Task 4: 数据模型

**Files:**
- Create: `game_core/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: 写失败测试 `tests/test_models.py`**

```python
from game_core.models import (
    InventoryItem, Player, make_new_player,
    MonsterDef, DropDef, EventDef, ItemDef, Balance, GameConfig,
    CombatResult, StepLog, ExploreResult,
)


def test_make_new_player_defaults():
    p = make_new_player("g1", "u1", "勇者", now=1000, start_hp=100)
    assert p.group_id == "g1"
    assert p.user_id == "u1"
    assert p.name == "勇者"
    assert p.level == 1
    assert p.current_hp == 100        # 新角色满血
    assert p.current_depth == 1
    assert p.max_depth == 1
    assert p.stamina == 0
    assert p.stamina_at == 1000
    assert p.inventory == []


def test_inventory_item_defaults():
    it = InventoryItem(item_id="hp_potion")
    assert it.quantity == 1
    assert it.equipped is False


def test_dataclasses_constructible():
    # 仅验证这些结构能被构造且字段存在
    DropDef(item="x", chance=0.1)
    MonsterDef(id="m", name="怪", depth_min=1, depth_max=5, hp=10,
               atk=1, defense=1, exp=5, gold_min=1, gold_max=2, drops=[])
    EventDef(id="e", type="flavor", weight=10)
    ItemDef(id="i", name="物", slot="weapon")
    Balance(stamina_regen_minutes=5, stamina_max=50, stamina_cost_per_step=5,
            base_exp=100, growth=1.4, stats_hp=20, stats_atk=3, stats_def=2,
            base_hp=100, base_atk=10, base_def=5, gold_loss_pct=0.1)
    CombatResult(won=True, rounds=2, damage_taken=5, hp_after=95)
    StepLog(kind="flavor", depth=2)
    ExploreResult(steps=[], total_gold=0, total_exp=0, items_gained=[],
                  level_ups=0, defeated=False, stamina_left=0,
                  depth_before=1, depth_after=1, hp_after=100, hp_max=100)
```

- [ ] **Step 2: 运行,确认失败**

Run: `pytest tests/test_models.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'game_core.models'`

- [ ] **Step 3: 写实现 `game_core/models.py`**

```python
from __future__ import annotations
from dataclasses import dataclass, field


# ---------- 配置模型(只读,来自 YAML) ----------

@dataclass
class DropDef:
    item: str
    chance: float


@dataclass
class MonsterDef:
    id: str
    name: str
    depth_min: int
    depth_max: int
    hp: int
    atk: int
    defense: int
    exp: int
    gold_min: int
    gold_max: int
    drops: list[DropDef] = field(default_factory=list)


@dataclass
class EventDef:
    id: str
    type: str                       # combat | treasure | trap | flavor
    weight: int
    depth_min: int = 1
    depth_max: int = 9999
    reward_gold: tuple[int, int] | None = None    # treasure
    damage_pct: float | None = None               # trap
    texts: list[str] = field(default_factory=list)  # flavor


@dataclass
class ItemDef:
    id: str
    name: str
    slot: str                       # weapon | armor | consumable
    atk: int = 0
    defense: int = 0
    hp: int = 0
    heal: int = 0
    rarity: str = "common"
    price: int | None = None        # 有 price 即可在商店出售


@dataclass
class Balance:
    stamina_regen_minutes: int
    stamina_max: int
    stamina_cost_per_step: int
    base_exp: int
    growth: float
    stats_hp: int
    stats_atk: int
    stats_def: int
    base_hp: int
    base_atk: int
    base_def: int
    gold_loss_pct: float


@dataclass
class GameConfig:
    balance: Balance
    monsters: dict[str, MonsterDef]
    events: list[EventDef]
    items: dict[str, ItemDef]


# ---------- 玩家状态(可变,内存表示) ----------

@dataclass
class InventoryItem:
    item_id: str
    quantity: int = 1
    equipped: bool = False


@dataclass
class Player:
    group_id: str
    user_id: str
    name: str
    level: int = 1
    exp: int = 0
    gold: int = 0
    stamina: int = 0
    stamina_at: int = 0             # unix 秒
    current_hp: int = 0
    current_depth: int = 1
    max_depth: int = 1
    created_at: int = 0
    last_active_at: int = 0
    inventory: list[InventoryItem] = field(default_factory=list)
    id: int | None = None           # DB 主键,持久化后才有


def make_new_player(group_id: str, user_id: str, name: str,
                    now: int, start_hp: int) -> Player:
    """创建一个满血、满层数=1 的新角色。start_hp 应为 1 级 hp_max。"""
    return Player(
        group_id=group_id, user_id=user_id, name=name,
        stamina=0, stamina_at=now, current_hp=start_hp,
        created_at=now, last_active_at=now,
    )


# ---------- 结果对象(系统计算输出,无中文排版) ----------

@dataclass
class CombatResult:
    won: bool
    rounds: int
    damage_taken: int
    hp_after: int
    reason: str = ""


@dataclass
class StepLog:
    kind: str                       # combat | treasure | trap | flavor
    depth: int
    monster: str | None = None
    won: bool | None = None
    rounds: int = 0
    gold: int = 0
    exp: int = 0
    items: list[str] = field(default_factory=list)
    hp_after: int = 0
    text: str = ""


@dataclass
class ExploreResult:
    steps: list[StepLog]
    total_gold: int
    total_exp: int
    items_gained: list[str]
    level_ups: int
    defeated: bool
    stamina_left: int
    depth_before: int
    depth_after: int
    hp_after: int
    hp_max: int
```

- [ ] **Step 4: 运行,确认通过**

Run: `pytest tests/test_models.py -v`
Expected: PASS(3 passed)

- [ ] **Step 5: Commit**

```bash
git add game_core/models.py tests/test_models.py
git commit -m "feat: 核心数据模型(配置/玩家/结果对象)"
```

---

## Task 5: 配置加载与校验

**Files:**
- Create: `game_core/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: 写失败测试 `tests/test_config.py`**

```python
import pytest
from pathlib import Path
from game_core.config import load_config, validate_config, ConfigError
from game_core.models import GameConfig

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def test_load_real_config():
    cfg = load_config(DATA_DIR)
    assert isinstance(cfg, GameConfig)
    assert cfg.balance.stamina_max == 50
    assert "slime" in cfg.monsters
    assert cfg.monsters["slime"].depth_min == 1
    assert cfg.monsters["slime"].depth_max == 5
    assert cfg.monsters["slime"].defense == 1     # YAML 的 def 映射到 defense
    assert "hp_potion" in cfg.items
    assert cfg.items["hp_potion"].heal == 50
    assert any(e.type == "combat" for e in cfg.events)


def test_validate_rejects_unknown_drop_item(tmp_path):
    cfg = load_config(DATA_DIR)
    cfg.monsters["slime"].drops.append(
        type(cfg.monsters["slime"].drops[0])(item="ghost_item", chance=0.1)
    )
    with pytest.raises(ConfigError, match="ghost_item"):
        validate_config(cfg)


def test_validate_rejects_nonpositive_weight():
    cfg = load_config(DATA_DIR)
    cfg.events[0].weight = 0
    with pytest.raises(ConfigError, match="weight"):
        validate_config(cfg)
```

- [ ] **Step 2: 运行,确认失败**

Run: `pytest tests/test_config.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'game_core.config'`

- [ ] **Step 3: 写实现 `game_core/config.py`**

```python
from __future__ import annotations
from pathlib import Path
import yaml

from game_core.models import (
    Balance, MonsterDef, DropDef, EventDef, ItemDef, GameConfig,
)

VALID_EVENT_TYPES = {"combat", "treasure", "trap", "flavor"}
VALID_SLOTS = {"weapon", "armor", "consumable"}


class ConfigError(Exception):
    """配置文件内容非法(启动时 fail fast)。"""


def _load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_config(data_dir: Path) -> GameConfig:
    data_dir = Path(data_dir)
    b = _load_yaml(data_dir / "balance.yaml")
    balance = Balance(
        stamina_regen_minutes=b["stamina"]["regen_minutes"],
        stamina_max=b["stamina"]["max"],
        stamina_cost_per_step=b["stamina"]["cost_per_step"],
        base_exp=b["leveling"]["base_exp"],
        growth=float(b["leveling"]["growth"]),
        stats_hp=b["stats_per_level"]["hp"],
        stats_atk=b["stats_per_level"]["atk"],
        stats_def=b["stats_per_level"]["def"],
        base_hp=b["base_stats"]["hp"],
        base_atk=b["base_stats"]["atk"],
        base_def=b["base_stats"]["def"],
        gold_loss_pct=float(b["defeat_penalty"]["gold_loss_pct"]),
    )

    monsters: dict[str, MonsterDef] = {}
    for m in _load_yaml(data_dir / "monsters.yaml"):
        drops = [DropDef(item=d["item"], chance=float(d["chance"]))
                 for d in m.get("drops", [])]
        monsters[m["id"]] = MonsterDef(
            id=m["id"], name=m["name"],
            depth_min=m["depth"][0], depth_max=m["depth"][1],
            hp=m["hp"], atk=m["atk"], defense=m["def"], exp=m["exp"],
            gold_min=m["gold"][0], gold_max=m["gold"][1], drops=drops,
        )

    events: list[EventDef] = []
    for e in _load_yaml(data_dir / "events.yaml"):
        reward = e.get("reward_gold")
        events.append(EventDef(
            id=e["id"], type=e["type"], weight=e["weight"],
            depth_min=e.get("depth_min", 1), depth_max=e.get("depth_max", 9999),
            reward_gold=(reward[0], reward[1]) if reward else None,
            damage_pct=e.get("damage_pct"),
            texts=e.get("texts", []),
        ))

    items: dict[str, ItemDef] = {}
    for it in _load_yaml(data_dir / "items.yaml"):
        items[it["id"]] = ItemDef(
            id=it["id"], name=it["name"], slot=it["slot"],
            atk=it.get("atk", 0), defense=it.get("def", 0),
            hp=it.get("hp", 0), heal=it.get("heal", 0),
            rarity=it.get("rarity", "common"), price=it.get("price"),
        )

    cfg = GameConfig(balance=balance, monsters=monsters, events=events, items=items)
    validate_config(cfg)
    return cfg


def validate_config(cfg: GameConfig) -> None:
    # 物品槽位合法
    for it in cfg.items.values():
        if it.slot not in VALID_SLOTS:
            raise ConfigError(f"物品 {it.id} 槽位非法: {it.slot}")
    # 怪物掉落引用的物品必须存在
    for m in cfg.monsters.values():
        if m.depth_min > m.depth_max:
            raise ConfigError(f"怪物 {m.id} 层数范围非法")
        for d in m.drops:
            if d.item not in cfg.items:
                raise ConfigError(f"怪物 {m.id} 掉落引用了不存在的物品: {d.item}")
            if not (0.0 <= d.chance <= 1.0):
                raise ConfigError(f"怪物 {m.id} 掉落概率非法: {d.chance}")
    # 事件类型与权重
    for e in cfg.events:
        if e.type not in VALID_EVENT_TYPES:
            raise ConfigError(f"事件 {e.id} 类型非法: {e.type}")
        if e.weight <= 0:
            raise ConfigError(f"事件 {e.id} 的 weight 必须为正")
    if not any(e.type == "combat" for e in cfg.events):
        raise ConfigError("至少需要一个 combat 事件")
```

- [ ] **Step 4: 运行,确认通过**

Run: `pytest tests/test_config.py -v`
Expected: PASS(3 passed)

- [ ] **Step 5: Commit**

```bash
git add game_core/config.py tests/test_config.py
git commit -m "feat: 配置加载与启动校验"
```

---

## Task 6: 派生属性

**Files:**
- Create: `game_core/stats.py`
- Test: `tests/test_stats.py`

- [ ] **Step 1: 写失败测试 `tests/test_stats.py`**

```python
from pathlib import Path
from game_core.config import load_config
from game_core.models import Player, InventoryItem
from game_core.stats import hp_max, attack, defense, power

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CFG = load_config(DATA_DIR)


def _player(level=1, inv=None):
    p = Player(group_id="g", user_id="u", name="勇者", level=level)
    p.inventory = inv or []
    return p


def test_base_stats_level_1():
    p = _player(level=1)
    assert hp_max(p, CFG) == 100      # base_hp
    assert attack(p, CFG) == 10       # base_atk
    assert defense(p, CFG) == 5       # base_def


def test_stats_grow_with_level():
    p = _player(level=3)              # +2 级
    assert hp_max(p, CFG) == 100 + 20 * 2
    assert attack(p, CFG) == 10 + 3 * 2
    assert defense(p, CFG) == 5 + 2 * 2


def test_equipped_items_add_stats():
    p = _player(level=1, inv=[
        InventoryItem(item_id="rusty_sword", equipped=True),   # atk +5
        InventoryItem(item_id="leather_armor", equipped=True), # def +4, hp +20
        InventoryItem(item_id="hp_potion", equipped=False),    # 未装备,不计
    ])
    assert attack(p, CFG) == 10 + 5
    assert defense(p, CFG) == 5 + 4
    assert hp_max(p, CFG) == 100 + 20


def test_power_formula():
    p = _player(level=1)
    # power = atk*2 + def*2 + hp_max*0.5 = 10*2 + 5*2 + 100*0.5 = 80
    assert power(p, CFG) == 80
```

- [ ] **Step 2: 运行,确认失败**

Run: `pytest tests/test_stats.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'game_core.stats'`

- [ ] **Step 3: 写实现 `game_core/stats.py`**

```python
from __future__ import annotations
from game_core.models import Player, GameConfig


def _equipped_defs(player: Player, cfg: GameConfig):
    for inv in player.inventory:
        if inv.equipped and inv.item_id in cfg.items:
            yield cfg.items[inv.item_id]


def hp_max(player: Player, cfg: GameConfig) -> int:
    b = cfg.balance
    base = b.base_hp + b.stats_hp * (player.level - 1)
    bonus = sum(d.hp for d in _equipped_defs(player, cfg))
    return base + bonus


def attack(player: Player, cfg: GameConfig) -> int:
    b = cfg.balance
    base = b.base_atk + b.stats_atk * (player.level - 1)
    bonus = sum(d.atk for d in _equipped_defs(player, cfg))
    return base + bonus


def defense(player: Player, cfg: GameConfig) -> int:
    b = cfg.balance
    base = b.base_def + b.stats_def * (player.level - 1)
    bonus = sum(d.defense for d in _equipped_defs(player, cfg))
    return base + bonus


def power(player: Player, cfg: GameConfig) -> int:
    return int(attack(player, cfg) * 2 + defense(player, cfg) * 2
               + hp_max(player, cfg) * 0.5)
```

- [ ] **Step 4: 运行,确认通过**

Run: `pytest tests/test_stats.py -v`
Expected: PASS(4 passed)

- [ ] **Step 5: Commit**

```bash
git add game_core/stats.py tests/test_stats.py
git commit -m "feat: 派生属性(hp_max/atk/def/power)"
```

---

## Task 7: 离线体力结算

**Files:**
- Create: `game_core/stamina.py`
- Test: `tests/test_stamina.py`

- [ ] **Step 1: 写失败测试 `tests/test_stamina.py`**

```python
from game_core.models import Player
from game_core.stamina import settle_stamina

REGEN_MIN = 5      # 每 5 分钟回 1
MAX = 50
STEP = 5 * 60      # 5 分钟的秒数


def _player(stamina, stamina_at):
    return Player(group_id="g", user_id="u", name="勇者",
                  stamina=stamina, stamina_at=stamina_at)


def test_no_time_passed_no_regen():
    p = _player(10, 1000)
    settle_stamina(p, now=1000, regen_minutes=REGEN_MIN, max_stamina=MAX)
    assert p.stamina == 10
    assert p.stamina_at == 1000


def test_partial_regen():
    p = _player(10, 1000)
    # 过了 17 分钟 → 回 3 点(整除),余 2 分钟保留
    settle_stamina(p, now=1000 + 17 * 60, regen_minutes=REGEN_MIN, max_stamina=MAX)
    assert p.stamina == 13
    # 时间戳推进 15 分钟(已兑现的 3 点),不是 17 分钟
    assert p.stamina_at == 1000 + 15 * 60


def test_caps_at_max_and_resets_timestamp():
    p = _player(48, 1000)
    # 过很久 → 应封顶在 50,且时间戳拉到 now
    now = 1000 + 999 * 60
    settle_stamina(p, now=now, regen_minutes=REGEN_MIN, max_stamina=MAX)
    assert p.stamina == MAX
    assert p.stamina_at == now


def test_remainder_not_lost_across_calls():
    p = _player(0, 1000)
    # 第一次:7 分钟 → 回 1,余 2 分钟
    settle_stamina(p, now=1000 + 7 * 60, regen_minutes=REGEN_MIN, max_stamina=MAX)
    assert p.stamina == 1
    # 第二次:再过 3 分钟(累计余 2+3=5)→ 再回 1
    settle_stamina(p, now=1000 + 10 * 60, regen_minutes=REGEN_MIN, max_stamina=MAX)
    assert p.stamina == 2
```

- [ ] **Step 2: 运行,确认失败**

Run: `pytest tests/test_stamina.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'game_core.stamina'`

- [ ] **Step 3: 写实现 `game_core/stamina.py`**

```python
from __future__ import annotations
from game_core.models import Player


def settle_stamina(player: Player, now: int,
                   regen_minutes: int, max_stamina: int) -> None:
    """按时间差现算离线体力回复;原地修改 player。"""
    elapsed_min = (now - player.stamina_at) // 60
    if elapsed_min < 0:
        elapsed_min = 0
    regen = elapsed_min // regen_minutes
    if regen > 0:
        player.stamina = min(max_stamina, player.stamina + regen)
        # 时间戳只推进"已兑现"的分钟,余数留到下次
        player.stamina_at += regen * regen_minutes * 60
    if player.stamina >= max_stamina:
        player.stamina = max_stamina
        player.stamina_at = now
```

- [ ] **Step 4: 运行,确认通过**

Run: `pytest tests/test_stamina.py -v`
Expected: PASS(4 passed)

- [ ] **Step 5: Commit**

```bash
git add game_core/stamina.py tests/test_stamina.py
git commit -m "feat: 离线体力结算(按时间差现算,余数不丢)"
```

---

## Task 8: 战斗结算

**Files:**
- Create: `game_core/combat.py`
- Test: `tests/test_combat.py`

- [ ] **Step 1: 写失败测试 `tests/test_combat.py`**

```python
import random
from game_core.models import MonsterDef, CombatResult
from game_core.combat import resolve_combat


def _monster(hp=30, atk=5, defense=1):
    return MonsterDef(id="m", name="怪", depth_min=1, depth_max=5,
                      hp=hp, atk=atk, defense=defense, exp=10,
                      gold_min=1, gold_max=3, drops=[])


def test_strong_player_always_wins():
    rng = random.Random(42)
    m = _monster(hp=10, atk=1, defense=0)
    r = resolve_combat(player_atk=50, player_def=50, player_hp=100,
                       monster=m, rng=rng)
    assert r.won is True
    assert r.hp_after == 100          # 怪打不动玩家(伤害最低 1,但秒杀前未被摸到)
    assert r.rounds >= 1


def test_weak_player_loses():
    rng = random.Random(1)
    m = _monster(hp=1000, atk=80, defense=50)
    r = resolve_combat(player_atk=10, player_def=1, player_hp=30,
                       monster=m, rng=rng)
    assert r.won is False
    assert r.hp_after <= 0


def test_minimum_damage_is_one():
    rng = random.Random(7)
    # 玩家攻击 5 远低于怪防御 100 → 仍应每回合至少造成 1 点,不会死循环
    m = _monster(hp=3, atk=1, defense=100)
    r = resolve_combat(player_atk=5, player_def=100, player_hp=100,
                       monster=m, rng=rng)
    assert r.won is True
    assert r.rounds <= 3              # 3 血、每次至少 1 → ≤3 回合


def test_deterministic_with_same_seed():
    m = _monster(hp=40, atk=10, defense=2)
    r1 = resolve_combat(20, 5, 50, m, random.Random(123))
    r2 = resolve_combat(20, 5, 50, m, random.Random(123))
    assert (r1.won, r1.rounds, r1.hp_after) == (r2.won, r2.rounds, r2.hp_after)
```

- [ ] **Step 2: 运行,确认失败**

Run: `pytest tests/test_combat.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'game_core.combat'`

- [ ] **Step 3: 写实现 `game_core/combat.py`**

```python
from __future__ import annotations
import random
from game_core.models import MonsterDef, CombatResult

MAX_ROUNDS = 50


def _hit(attacker_atk: int, defender_def: int, rng: random.Random) -> int:
    raw = max(1, attacker_atk - defender_def)
    return max(1, round(raw * rng.uniform(0.9, 1.1)))


def resolve_combat(player_atk: int, player_def: int, player_hp: int,
                   monster: MonsterDef, rng: random.Random) -> CombatResult:
    """自动回合制结算。返回胜负、回合数、受到的总伤害、剩余 HP。"""
    mhp = monster.hp
    start_hp = player_hp
    hp = player_hp
    for r in range(1, MAX_ROUNDS + 1):
        # 玩家先手
        mhp -= _hit(player_atk, monster.defense, rng)
        if mhp <= 0:
            return CombatResult(won=True, rounds=r,
                                damage_taken=start_hp - hp, hp_after=hp)
        # 怪反击
        hp -= _hit(monster.atk, player_def, rng)
        if hp <= 0:
            return CombatResult(won=False, rounds=r,
                                damage_taken=start_hp - hp, hp_after=hp)
    return CombatResult(won=False, rounds=MAX_ROUNDS,
                        damage_taken=start_hp - hp, hp_after=hp,
                        reason="缠斗过久撤退")
```

- [ ] **Step 4: 运行,确认通过**

Run: `pytest tests/test_combat.py -v`
Expected: PASS(4 passed)

- [ ] **Step 5: Commit**

```bash
git add game_core/combat.py tests/test_combat.py
git commit -m "feat: 战斗结算(回合制数值,最低1伤,50回合上限)"
```

---

## Task 9: 成长与重伤回城

**Files:**
- Create: `game_core/progression.py`
- Test: `tests/test_progression.py`

- [ ] **Step 1: 写失败测试 `tests/test_progression.py`**

```python
from pathlib import Path
from game_core.config import load_config
from game_core.models import Player
from game_core.progression import exp_need, grant_exp, apply_defeat
from game_core.stats import hp_max

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CFG = load_config(DATA_DIR)


def _player(level=1, exp=0, gold=0, hp=None):
    p = Player(group_id="g", user_id="u", name="勇者", level=level,
               exp=exp, gold=gold, current_depth=5, max_depth=8)
    p.current_hp = hp if hp is not None else hp_max(p, CFG)
    return p


def test_exp_need_curve():
    assert exp_need(1, CFG) == 100                  # base_exp
    assert exp_need(2, CFG) == round(100 * 1.4)     # 140
    assert exp_need(3, CFG) == round(100 * 1.4 ** 2)


def test_grant_exp_single_level():
    p = _player(level=1, exp=0)
    ups = grant_exp(p, 100, CFG)
    assert ups == 1
    assert p.level == 2
    assert p.exp == 0


def test_grant_exp_multi_level_in_one_call():
    p = _player(level=1, exp=0)
    # 100 + 140 = 240 足够升到 3 级,剩 0
    ups = grant_exp(p, 240, CFG)
    assert ups == 2
    assert p.level == 3
    assert p.exp == 0


def test_level_up_full_heals():
    p = _player(level=1, hp=10)         # 残血
    grant_exp(p, 100, CFG)
    assert p.current_hp == hp_max(p, CFG)   # 升级回满血


def test_apply_defeat_penalty():
    p = _player(level=3, gold=200, hp=1)
    apply_defeat(p, CFG)
    assert p.gold == 180                # 损失 10%
    assert p.current_depth == 1         # 回到第 1 层
    assert p.max_depth == 8             # 历史最深保留
    assert p.current_hp == hp_max(p, CFG)   # 满血回城
```

- [ ] **Step 2: 运行,确认失败**

Run: `pytest tests/test_progression.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'game_core.progression'`

- [ ] **Step 3: 写实现 `game_core/progression.py`**

```python
from __future__ import annotations
from game_core.models import Player, GameConfig
from game_core.stats import hp_max


def exp_need(level: int, cfg: GameConfig) -> int:
    """从 level 升到 level+1 所需经验。"""
    b = cfg.balance
    return round(b.base_exp * (b.growth ** (level - 1)))


def grant_exp(player: Player, amount: int, cfg: GameConfig) -> int:
    """给予经验,处理连续升级。返回升级次数。升级时回满血。"""
    player.exp += amount
    level_ups = 0
    while player.exp >= exp_need(player.level, cfg):
        player.exp -= exp_need(player.level, cfg)
        player.level += 1
        level_ups += 1
    if level_ups > 0:
        player.current_hp = hp_max(player, cfg)
    return level_ups


def apply_defeat(player: Player, cfg: GameConfig) -> None:
    """重伤回城:损失金币、回到第 1 层、满血。max_depth 保留。"""
    player.gold -= int(player.gold * cfg.balance.gold_loss_pct)
    player.current_depth = 1
    player.current_hp = hp_max(player, cfg)
```

- [ ] **Step 4: 运行,确认通过**

Run: `pytest tests/test_progression.py -v`
Expected: PASS(5 passed)

- [ ] **Step 5: Commit**

```bash
git add game_core/progression.py tests/test_progression.py
git commit -m "feat: 经验曲线/升级回满血/重伤回城"
```

---

## Task 10: 掉落、背包与装备

**Files:**
- Create: `game_core/loot.py`
- Test: `tests/test_loot.py`

- [ ] **Step 1: 写失败测试 `tests/test_loot.py`**

```python
import random
import pytest
from pathlib import Path
from game_core.config import load_config
from game_core.models import Player, InventoryItem, MonsterDef, DropDef
from game_core.loot import roll_drops, add_item, equip, unequip, use_item
from game_core.stats import hp_max
from game_core.errors import ItemNotFound, InvalidSlot

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CFG = load_config(DATA_DIR)


def _player():
    p = Player(group_id="g", user_id="u", name="勇者")
    p.current_hp = hp_max(p, CFG)
    return p


def test_roll_drops_respects_chance():
    m = MonsterDef(id="m", name="怪", depth_min=1, depth_max=5, hp=10, atk=1,
                   defense=1, exp=5, gold_min=1, gold_max=2,
                   drops=[DropDef(item="rusty_sword", chance=1.0),
                          DropDef(item="hp_potion", chance=0.0)])
    got = roll_drops(m, random.Random(0))
    assert got == ["rusty_sword"]      # chance=1 必掉,chance=0 必不掉


def test_add_item_stacks():
    p = _player()
    add_item(p, "hp_potion")
    add_item(p, "hp_potion")
    pots = [i for i in p.inventory if i.item_id == "hp_potion"]
    assert len(pots) == 1
    assert pots[0].quantity == 2


def test_equip_and_unequip():
    p = _player()
    add_item(p, "rusty_sword")
    equip(p, "rusty_sword", CFG)
    assert any(i.item_id == "rusty_sword" and i.equipped for i in p.inventory)
    unequip(p, "rusty_sword", CFG)
    assert all(not i.equipped for i in p.inventory)


def test_equip_replaces_same_slot():
    p = _player()
    add_item(p, "rusty_sword")
    add_item(p, "iron_sword")
    equip(p, "rusty_sword", CFG)
    equip(p, "iron_sword", CFG)        # 同为 weapon,应自动换下旧的
    equipped = [i.item_id for i in p.inventory if i.equipped]
    assert equipped == ["iron_sword"]


def test_equip_consumable_rejected():
    p = _player()
    add_item(p, "hp_potion")
    with pytest.raises(InvalidSlot):
        equip(p, "hp_potion", CFG)


def test_equip_missing_item_raises():
    p = _player()
    with pytest.raises(ItemNotFound):
        equip(p, "rusty_sword", CFG)


def test_use_potion_heals_and_consumes():
    p = _player()
    p.current_hp = 10
    add_item(p, "hp_potion")
    use_item(p, "hp_potion", CFG)
    assert p.current_hp == min(hp_max(p, CFG), 10 + 50)
    assert all(i.item_id != "hp_potion" for i in p.inventory)   # 用完移除


def test_use_caps_at_hp_max():
    p = _player()
    p.current_hp = hp_max(p, CFG) - 5
    add_item(p, "hp_potion")
    use_item(p, "hp_potion", CFG)
    assert p.current_hp == hp_max(p, CFG)
```

- [ ] **Step 2: 运行,确认失败**

Run: `pytest tests/test_loot.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'game_core.loot'`

- [ ] **Step 3: 写实现 `game_core/loot.py`**

```python
from __future__ import annotations
import random
from game_core.models import Player, MonsterDef, GameConfig, InventoryItem
from game_core.errors import ItemNotFound, InvalidSlot
from game_core.stats import hp_max


def roll_drops(monster: MonsterDef, rng: random.Random) -> list[str]:
    return [d.item for d in monster.drops if rng.random() < d.chance]


def _find(player: Player, item_id: str) -> InventoryItem | None:
    for inv in player.inventory:
        if inv.item_id == item_id:
            return inv
    return None


def add_item(player: Player, item_id: str, qty: int = 1) -> None:
    existing = _find(player, item_id)
    if existing and not existing.equipped:
        existing.quantity += qty
    else:
        player.inventory.append(InventoryItem(item_id=item_id, quantity=qty))


def equip(player: Player, item_id: str, cfg: GameConfig) -> None:
    if item_id not in cfg.items:
        raise ItemNotFound(f"未知物品: {item_id}")
    slot = cfg.items[item_id].slot
    if slot not in ("weapon", "armor"):
        raise InvalidSlot(f"{cfg.items[item_id].name} 不能装备")
    inv = _find(player, item_id)
    if inv is None:
        raise ItemNotFound(f"背包里没有 {item_id}")
    # 卸下同槽位的其它装备
    for other in player.inventory:
        if other.equipped and cfg.items[other.item_id].slot == slot:
            other.equipped = False
    inv.equipped = True


def unequip(player: Player, item_id: str, cfg: GameConfig) -> None:
    inv = _find(player, item_id)
    if inv is None or not inv.equipped:
        raise ItemNotFound(f"{item_id} 未装备")
    inv.equipped = False


def use_item(player: Player, item_id: str, cfg: GameConfig) -> None:
    if item_id not in cfg.items:
        raise ItemNotFound(f"未知物品: {item_id}")
    item = cfg.items[item_id]
    if item.slot != "consumable":
        raise InvalidSlot(f"{item.name} 不是消耗品")
    inv = _find(player, item_id)
    if inv is None:
        raise ItemNotFound(f"背包里没有 {item.name}")
    if item.heal > 0:
        player.current_hp = min(hp_max(player, cfg), player.current_hp + item.heal)
    inv.quantity -= 1
    if inv.quantity <= 0:
        player.inventory.remove(inv)
```

- [ ] **Step 4: 运行,确认通过**

Run: `pytest tests/test_loot.py -v`
Expected: PASS(8 passed)

- [ ] **Step 5: Commit**

```bash
git add game_core/loot.py tests/test_loot.py
git commit -m "feat: 掉落/背包堆叠/装备切换/消耗品使用"
```

---

## Task 11: 商店

**Files:**
- Create: `game_core/shop.py`
- Test: `tests/test_shop.py`

- [ ] **Step 1: 写失败测试 `tests/test_shop.py`**

```python
import pytest
from pathlib import Path
from game_core.config import load_config
from game_core.models import Player
from game_core.shop import list_shop, buy
from game_core.errors import NotEnoughGold, ItemNotFound

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CFG = load_config(DATA_DIR)


def test_list_shop_only_priced_items():
    items = list_shop(CFG)
    ids = {i.id for i in items}
    assert "hp_potion" in ids          # 有 price
    assert all(i.price is not None for i in items)


def test_buy_deducts_gold_and_adds_item():
    p = Player(group_id="g", user_id="u", name="勇者", gold=100)
    buy(p, "hp_potion", CFG)           # price 20
    assert p.gold == 80
    assert any(i.item_id == "hp_potion" for i in p.inventory)


def test_buy_insufficient_gold():
    p = Player(group_id="g", user_id="u", name="勇者", gold=10)
    with pytest.raises(NotEnoughGold):
        buy(p, "hp_potion", CFG)       # 需 20
    assert p.gold == 10                # 失败不扣钱


def test_buy_unknown_item():
    p = Player(group_id="g", user_id="u", name="勇者", gold=999)
    with pytest.raises(ItemNotFound):
        buy(p, "dragon_egg", CFG)
```

- [ ] **Step 2: 运行,确认失败**

Run: `pytest tests/test_shop.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'game_core.shop'`

- [ ] **Step 3: 写实现 `game_core/shop.py`**

```python
from __future__ import annotations
from game_core.models import Player, GameConfig, ItemDef
from game_core.loot import add_item
from game_core.errors import NotEnoughGold, ItemNotFound


def list_shop(cfg: GameConfig) -> list[ItemDef]:
    """所有标了 price 的物品即在售。"""
    return [it for it in cfg.items.values() if it.price is not None]


def buy(player: Player, item_id: str, cfg: GameConfig) -> None:
    item = cfg.items.get(item_id)
    if item is None or item.price is None:
        raise ItemNotFound(f"商店没有这件商品: {item_id}")
    if player.gold < item.price:
        raise NotEnoughGold(f"金币不足(需 {item.price},当前 {player.gold})")
    player.gold -= item.price
    add_item(player, item_id)
```

- [ ] **Step 4: 运行,确认通过**

Run: `pytest tests/test_shop.py -v`
Expected: PASS(4 passed)

- [ ] **Step 5: Commit**

```bash
git add game_core/shop.py tests/test_shop.py
git commit -m "feat: 商店列表与购买"
```

---

## Task 12: 排行榜排序

**Files:**
- Create: `game_core/ranking.py`
- Test: `tests/test_ranking.py`

- [ ] **Step 1: 写失败测试 `tests/test_ranking.py`**

```python
from game_core.models import Player
from game_core.ranking import rank_players


def _p(name, level, max_depth):
    return Player(group_id="g", user_id=name, name=name,
                  level=level, max_depth=max_depth)


def test_rank_by_level_then_depth():
    players = [_p("A", 3, 5), _p("B", 5, 2), _p("C", 5, 9)]
    ranked = rank_players(players, key="level", limit=10)
    assert [p.name for p in ranked] == ["C", "B", "A"]   # 5级C(深9)>5级B(深2)>3级A


def test_rank_by_depth():
    players = [_p("A", 3, 5), _p("B", 5, 2), _p("C", 5, 9)]
    ranked = rank_players(players, key="depth", limit=10)
    assert [p.name for p in ranked] == ["C", "A", "B"]   # 深 9 > 5 > 2


def test_limit_applies():
    players = [_p(str(i), i, i) for i in range(1, 21)]
    ranked = rank_players(players, key="level", limit=10)
    assert len(ranked) == 10
    assert ranked[0].name == "20"
```

- [ ] **Step 2: 运行,确认失败**

Run: `pytest tests/test_ranking.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'game_core.ranking'`

- [ ] **Step 3: 写实现 `game_core/ranking.py`**

```python
from __future__ import annotations
from game_core.models import Player


def rank_players(players: list[Player], key: str = "level",
                 limit: int = 10) -> list[Player]:
    """对(同群的)玩家列表排序取前 limit 名。

    key="level": 先比等级,再比 max_depth。
    key="depth": 比 max_depth,再比等级。
    """
    if key == "depth":
        sort_key = lambda p: (p.max_depth, p.level)
    else:
        sort_key = lambda p: (p.level, p.max_depth)
    return sorted(players, key=sort_key, reverse=True)[:limit]
```

- [ ] **Step 4: 运行,确认通过**

Run: `pytest tests/test_ranking.py -v`
Expected: PASS(3 passed)

- [ ] **Step 5: Commit**

```bash
git add game_core/ranking.py tests/test_ranking.py
git commit -m "feat: 排行榜排序(等级榜/深度榜)"
```

---

## Task 13: 探索循环(组合系统)

**Files:**
- Create: `game_core/exploration.py`
- Test: `tests/test_exploration.py`

- [ ] **Step 1: 写失败测试 `tests/test_exploration.py`**

```python
import random
from pathlib import Path
from game_core.config import load_config
from game_core.models import Player
from game_core.stats import hp_max
from game_core.exploration import explore

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CFG = load_config(DATA_DIR)


def _player(stamina, now=10_000, level=1):
    p = Player(group_id="g", user_id="u", name="勇者",
               level=level, stamina=stamina, stamina_at=now)
    p.current_hp = hp_max(p, CFG)
    return p


def test_no_stamina_means_no_steps():
    p = _player(stamina=0)
    res = explore(p, CFG, now=p.stamina_at, rng=random.Random(0))
    assert res.steps == []
    assert res.stamina_left == 0


def test_explore_consumes_stamina_in_steps():
    # 体力 10,每步耗 5 → 恰好 2 步(无中途战败时)
    p = _player(stamina=10)
    res = explore(p, CFG, now=p.stamina_at, rng=random.Random(2))
    assert res.stamina_left < 10
    assert p.stamina == res.stamina_left
    # 步数 = 消耗的体力 / 5,且 ≤ 2
    assert 1 <= len(res.steps) <= 2


def test_offline_stamina_settled_before_exploring():
    # 初始 0 体力,但已过去 60 分钟(每5分钟+1 → +12)
    p = _player(stamina=0, now=10_000)
    later = 10_000 + 60 * 60
    res = explore(p, CFG, now=later, rng=random.Random(3))
    # 先结算出 12 体力,够走 2 步(每步5),最终应有探索发生
    assert len(res.steps) >= 1


def test_max_depth_tracks_progress():
    p = _player(stamina=50, level=50)   # 高级保证不会战败
    start_max = p.max_depth
    res = explore(p, CFG, now=p.stamina_at, rng=random.Random(5))
    assert res.depth_after >= res.depth_before
    assert p.max_depth >= start_max
    assert p.max_depth == max(start_max, res.depth_after)


def test_defeat_resets_depth_to_one():
    # 1 级、深处、塞满体力,对上强怪极可能战败;遍历多个种子找到一次战败
    defeated_seen = False
    for seed in range(50):
        p = Player(group_id="g", user_id="u", name="勇者",
                   level=1, stamina=50, stamina_at=0,
                   current_depth=15, max_depth=15)
        p.current_hp = hp_max(p, CFG)
        res = explore(p, CFG, now=0, rng=random.Random(seed))
        if res.defeated:
            defeated_seen = True
            assert p.current_depth == 1        # 回城
            assert p.max_depth >= 15           # 历史最深保留
            assert p.current_hp == hp_max(p, CFG)
            break
    assert defeated_seen, "50 个种子内应至少出现一次战败"


def test_result_totals_are_consistent():
    p = _player(stamina=50, level=80)   # 高级,稳赢,稳定积累
    res = explore(p, CFG, now=p.stamina_at, rng=random.Random(11))
    assert res.total_exp == sum(s.exp for s in res.steps)
    assert res.total_gold == sum(s.gold for s in res.steps)
    assert res.hp_max == hp_max(p, CFG)
```

- [ ] **Step 2: 运行,确认失败**

Run: `pytest tests/test_exploration.py -v`
Expected: FAIL,`ModuleNotFoundError: No module named 'game_core.exploration'`

- [ ] **Step 3: 写实现 `game_core/exploration.py`**

```python
from __future__ import annotations
import random
from game_core.models import Player, GameConfig, StepLog, ExploreResult
from game_core import stats, stamina as stamina_mod, combat, progression, loot


def _pick_event(cfg: GameConfig, depth: int, rng: random.Random):
    pool = [e for e in cfg.events if e.depth_min <= depth <= e.depth_max]
    weights = [e.weight for e in pool]
    return rng.choices(pool, weights=weights, k=1)[0]


def _pick_monster(cfg: GameConfig, depth: int, rng: random.Random):
    pool = [m for m in cfg.monsters.values()
            if m.depth_min <= depth <= m.depth_max]
    if not pool:
        # 超出所有怪物层数范围时,回退到层数范围最高的怪
        pool = [max(cfg.monsters.values(), key=lambda m: m.depth_max)]
    return rng.choice(pool)


def explore(player: Player, cfg: GameConfig, now: int,
            rng: random.Random) -> ExploreResult:
    b = cfg.balance
    stamina_mod.settle_stamina(player, now, b.stamina_regen_minutes, b.stamina_max)
    player.last_active_at = now

    steps: list[StepLog] = []
    total_gold = total_exp = level_ups = 0
    items_gained: list[str] = []
    defeated = False
    depth_before = player.current_depth

    while player.stamina >= b.stamina_cost_per_step:
        player.stamina -= b.stamina_cost_per_step
        depth = player.current_depth
        event = _pick_event(cfg, depth, rng)

        if event.type == "combat":
            monster = _pick_monster(cfg, depth, rng)
            res = combat.resolve_combat(
                stats.attack(player, cfg), stats.defense(player, cfg),
                player.current_hp, monster, rng)
            player.current_hp = res.hp_after
            if not res.won:
                progression.apply_defeat(player, cfg)
                steps.append(StepLog(kind="combat", depth=depth,
                                     monster=monster.name, won=False,
                                     rounds=res.rounds, hp_after=player.current_hp))
                defeated = True
                break
            gold = rng.randint(monster.gold_min, monster.gold_max)
            drops = loot.roll_drops(monster, rng)
            for item_id in drops:
                loot.add_item(player, item_id)
                items_gained.append(item_id)
            player.gold += gold
            ups = progression.grant_exp(player, monster.exp, cfg)
            level_ups += ups
            total_gold += gold
            total_exp += monster.exp
            player.current_depth += 1
            steps.append(StepLog(kind="combat", depth=depth, monster=monster.name,
                                 won=True, rounds=res.rounds, gold=gold,
                                 exp=monster.exp, items=drops,
                                 hp_after=player.current_hp))

        elif event.type == "treasure":
            lo, hi = event.reward_gold or (0, 0)
            gold = rng.randint(lo, hi)
            player.gold += gold
            total_gold += gold
            player.current_depth += 1
            steps.append(StepLog(kind="treasure", depth=depth,
                                 gold=gold, hp_after=player.current_hp))

        elif event.type == "trap":
            dmg = int(stats.hp_max(player, cfg) * (event.damage_pct or 0))
            player.current_hp -= dmg
            if player.current_hp <= 0:
                progression.apply_defeat(player, cfg)
                steps.append(StepLog(kind="trap", depth=depth,
                                     hp_after=player.current_hp,
                                     text=f"踩中陷阱 -{dmg}"))
                defeated = True
                break
            player.current_depth += 1
            steps.append(StepLog(kind="trap", depth=depth,
                                 hp_after=player.current_hp,
                                 text=f"踩中陷阱 -{dmg}"))

        else:  # flavor
            text = rng.choice(event.texts) if event.texts else ""
            player.current_depth += 1
            steps.append(StepLog(kind="flavor", depth=depth, text=text,
                                 hp_after=player.current_hp))

        player.max_depth = max(player.max_depth, player.current_depth)

    return ExploreResult(
        steps=steps, total_gold=total_gold, total_exp=total_exp,
        items_gained=items_gained, level_ups=level_ups, defeated=defeated,
        stamina_left=player.stamina, depth_before=depth_before,
        depth_after=player.current_depth, hp_after=player.current_hp,
        hp_max=stats.hp_max(player, cfg),
    )
```

- [ ] **Step 4: 运行,确认通过**

Run: `pytest tests/test_exploration.py -v`
Expected: PASS(6 passed)

- [ ] **Step 5: Commit**

```bash
git add game_core/exploration.py tests/test_exploration.py
git commit -m "feat: 探索循环(体力结算→抽事件→战斗/宝箱/陷阱/叙事→结算)"
```

---

## Task 14: 引擎端到端冒烟测试

**Files:**
- Test: `tests/test_engine_smoke.py`

验证整个引擎能跑通一段完整生命周期,且各系统协作无类型/接口错配。

- [ ] **Step 1: 写测试 `tests/test_engine_smoke.py`**

```python
import random
from pathlib import Path
from game_core.config import load_config
from game_core.models import make_new_player
from game_core.stats import hp_max
from game_core.exploration import explore
from game_core.shop import buy
from game_core.loot import equip
from game_core.ranking import rank_players

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CFG = load_config(DATA_DIR)


def test_full_lifecycle():
    rng = random.Random(2026)
    now = 0
    p = make_new_player("group1", "userA", "小明",
                        now=now, start_hp=hp_max_for_new())

    # 挂机 5 小时 → 体力回满,连续探索若干轮
    for hours in range(1, 6):
        now = hours * 3600
        res = explore(p, CFG, now=now, rng=rng)
        assert res.hp_max == hp_max(p, CFG)
        assert res.depth_after >= 1

    # 攒了金币就买把剑并装备(若买得起)
    if p.gold >= CFG.items["rusty_sword"].price:
        buy(p, "rusty_sword", CFG)
        equip(p, "rusty_sword", CFG)
        # 装备后攻击力应高于基础
        from game_core.stats import attack
        assert attack(p, CFG) > CFG.balance.base_atk

    # 排行榜:把自己和两个假人一起排
    others = [
        make_new_player("group1", "userB", "小红", now=0, start_hp=100),
        make_new_player("group1", "userC", "小刚", now=0, start_hp=100),
    ]
    ranked = rank_players([p, *others], key="level", limit=10)
    assert p in ranked
    assert len(ranked) == 3


def hp_max_for_new() -> int:
    # 1 级新角色的 hp_max = base_hp
    return CFG.balance.base_hp
```

- [ ] **Step 2: 运行,确认通过**

Run: `pytest tests/test_engine_smoke.py -v`
Expected: PASS(1 passed)

- [ ] **Step 3: 运行全部测试,确认引擎整体绿灯**

Run: `pytest`
Expected: 所有测试通过(约 40+ 项)。

- [ ] **Step 4: Commit**

```bash
git add tests/test_engine_smoke.py
git commit -m "test: 引擎端到端冒烟(完整角色生命周期)"
```

---

## 完成标准

- [ ] `pytest` 全绿。
- [ ] 能在 `python` REPL 里:`load_config` → `make_new_player` → `explore` → `buy`/`equip` → `rank_players` 全程跑通。
- [ ] `game_core/` 下任何模块都没有 `import nonebot` / 没有 SQLite / 没有中文消息排版。

完成后进入**计划二:存储(SQLite 仓储)+ 机器人接入(formatting / NoneBot2 插件 / OneBot 联调)**。

---

## 非目标(本计划不做)

- SQLite 持久化、仓储层(计划二)
- 中文消息格式化、NoneBot 指令插件、OneBot 部署(计划二)
- 战力榜、PvP、组队、手写剧情(v2+)
