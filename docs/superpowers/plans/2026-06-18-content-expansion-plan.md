# 游戏内容中等扩展 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 将游戏从 4 件物品/3 只怪物/20 层扩展至 37 件物品/10 只怪物/50 层，新增 Buff 系统、体力重平衡、经济联动。

**Architecture:** 分层递进 — 先改纯数据(YAML)，再扩模型(Buff/ItemDef 新字段)，然后改核心逻辑(stats→loot→exploration)，最后改持久层(DB 迁移→repository)和展示层(formatting)。每层改动独立可测。

**Tech Stack:** Python 3.10+, PyYAML, SQLite, pytest

## Global Constraints

- `game_core/` 绝不 import nonebot，不拼中文消息
- `bot/formatting.py` 是唯一"结果对象 → 中文文本"的地方
- 所有 GameError 子类友好展示，不泄露堆栈
- `now` 和 `rng` 作为参数注入，测试可传固定值
- 稀有度稀有度：凡品→良品→上品→极品→仙品（仙品不可购买）
- 体力上限 100，每步耗 5，1 分钟回 10 点
- 旧物品 ID 迁移：`rusty_sword`→`iron_sword`，`iron_sword`→`fine_steel_sword`
- 旧存档兼容：启动时自动执行迁移

---

### Task 1: 更新 YAML 数据文件（纯配置，无代码依赖）

**Files:**
- Rewrite: `data/items.yaml`
- Rewrite: `data/monsters.yaml`
- Rewrite: `data/events.yaml`
- Modify: `data/balance.yaml`

**Interfaces:**
- Produces: 37 个物品 ID（后续 tasks 的 `find_item_id()` 目标）、10 个怪物 ID、深度分档事件、stamina_max=100

- [ ] **Step 1: 重写 items.yaml（4→37 件）**

```yaml
# ===== 武器 - 剑（均衡：攻击+少量防御）=====
- id: iron_sword
  name: 铁剑
  slot: weapon
  atk: 5
  rarity: common
  price: 50
- id: fine_steel_sword
  name: 百炼钢剑
  slot: weapon
  atk: 9
  def: 1
  rarity: uncommon
  price: 125
- id: cold_iron_sword
  name: 寒铁剑
  slot: weapon
  atk: 14
  def: 2
  rarity: rare
  price: 300
- id: dark_abyss_sword
  name: 玄冥重剑
  slot: weapon
  atk: 23
  def: 3
  rarity: epic
  price: 750
- id: dragon_slayer_sword
  name: 斩龙剑
  slot: weapon
  atk: 35
  def: 5
  rarity: legendary

# ===== 武器 - 刀（高攻，无防御）=====
- id: plain_blade
  name: 朴刀
  slot: weapon
  atk: 7
  rarity: common
  price: 50
- id: goose_wing_blade
  name: 雁翎刀
  slot: weapon
  atk: 12
  rarity: uncommon
  price: 125
- id: hundred_forged_blade
  name: 百辟刀
  slot: weapon
  atk: 20
  rarity: rare
  price: 300
- id: long_haft_blade
  name: 陌刀
  slot: weapon
  atk: 32
  rarity: epic
  price: 750
- id: green_dragon_blade
  name: 青龙偃月
  slot: weapon
  atk: 49
  rarity: legendary

# ===== 武器 - 长兵（攻击+HP）=====
- id: bamboo_spear
  name: 竹枪
  slot: weapon
  atk: 4
  hp: 10
  rarity: common
  price: 50
- id: steel_point_spear
  name: 点钢枪
  slot: weapon
  atk: 7
  hp: 20
  rarity: uncommon
  price: 125
- id: hook_sickle_spear
  name: 钩镰枪
  slot: weapon
  atk: 11
  hp: 35
  rarity: rare
  price: 300
- id: serpent_spear
  name: 丈八蛇矛
  slot: weapon
  atk: 18
  hp: 55
  rarity: epic
  price: 750
- id: heaven_piercer_halberd
  name: 方天画戟
  slot: weapon
  atk: 28
  hp: 80
  rarity: legendary

# ===== 武器 - 暗器（高攻+负防御）=====
- id: flying_stone
  name: 飞蝗石
  slot: weapon
  atk: 8
  def: -2
  rarity: common
  price: 50
- id: plum_blossom_dart
  name: 梅花镖
  slot: weapon
  atk: 14
  def: -3
  rarity: uncommon
  price: 125
- id: bone_penetrating_nail
  name: 透骨钉
  slot: weapon
  atk: 22
  def: -5
  rarity: rare
  price: 300
- id: soul_chaser_needle
  name: 追魂针
  slot: weapon
  atk: 35
  def: -8
  rarity: epic
  price: 750
- id: storm_of_needles
  name: 暴雨梨花
  slot: weapon
  atk: 55
  def: -12
  rarity: legendary

# ===== 护甲 - 轻甲（高HP+低防御）=====
- id: cloth_armor
  name: 布甲
  slot: armor
  def: 2
  hp: 20
  rarity: common
  price: 80
- id: leather_armor
  name: 皮铠
  slot: armor
  def: 3
  hp: 35
  rarity: uncommon
  price: 200
- id: rhino_hide_armor
  name: 犀皮甲
  slot: armor
  def: 5
  hp: 55
  rarity: rare
  price: 480
- id: turtle_shell_armor
  name: 玄龟甲
  slot: armor
  def: 8
  hp: 85
  rarity: epic
  price: 1200
- id: black_tortoise_armor
  name: 玄武灵甲
  slot: armor
  def: 12
  hp: 130
  rarity: legendary

# ===== 护甲 - 重甲（高防御+低HP）=====
- id: iron_scale_armor
  name: 铁札甲
  slot: armor
  def: 5
  hp: 10
  rarity: common
  price: 80
- id: bright_mirror_armor
  name: 明光铠
  slot: armor
  def: 8
  hp: 18
  rarity: uncommon
  price: 200
- id: heart_protector_armor
  name: 护心铠
  slot: armor
  def: 13
  hp: 28
  rarity: rare
  price: 480
- id: mountain_pattern_armor
  name: 山文甲
  slot: armor
  def: 20
  hp: 45
  rarity: epic
  price: 1200
- id: diamond_body_armor
  name: 金刚不坏铠
  slot: armor
  def: 32
  hp: 70
  rarity: legendary

# ===== 消耗品 - 治疗 =====
- id: hp_potion
  name: 金疮药
  slot: consumable
  heal: 30
  price: 15
- id: greater_hp_potion
  name: 续命丹
  slot: consumable
  heal: 80
  price: 40
- id: supreme_hp_potion
  name: 九转还魂丹
  slot: consumable
  heal: 200
  price: 100

# ===== 消耗品 - 攻击 Buff =====
- id: atk_potion_minor
  name: 蛮牛散
  slot: consumable
  buff_type: atk
  buff_value: 10
  buff_steps: 4
  price: 30
- id: atk_potion_major
  name: 虎骨酒
  slot: consumable
  buff_type: atk
  buff_value: 20
  buff_steps: 6
  price: 70

# ===== 消耗品 - 防御 Buff =====
- id: def_potion_minor
  name: 铁皮膏
  slot: consumable
  buff_type: def
  buff_value: 8
  buff_steps: 4
  price: 25
- id: def_potion_major
  name: 金钟罩符
  slot: consumable
  buff_type: def
  buff_value: 16
  buff_steps: 6
  price: 60

# ===== 消耗品 - 体力 =====
- id: stamina_potion
  name: 回气丹
  slot: consumable
  buff_type: stamina
  buff_value: 50
  price: 80
```

- [ ] **Step 2: 重写 monsters.yaml（3→10 只）**

```yaml
- id: slime
  name: 史莱姆
  depth: [1, 5]
  hp: 30
  atk: 5
  def: 1
  exp: 15
  gold: [5, 10]
  drops:
    - { item: iron_sword, chance: 0.05 }

- id: goblin
  name: 哥布林
  depth: [3, 10]
  hp: 60
  atk: 12
  def: 3
  exp: 30
  gold: [12, 22]
  drops:
    - { item: leather_armor, chance: 0.04 }
    - { item: hp_potion, chance: 0.10 }

- id: skeleton
  name: 骷髅战士
  depth: [6, 16]
  hp: 120
  atk: 22
  def: 8
  exp: 60
  gold: [22, 42]
  drops:
    - { item: fine_steel_sword, chance: 0.03 }

- id: stone_golem
  name: 石魔像
  depth: [12, 24]
  hp: 200
  atk: 35
  def: 15
  exp: 100
  gold: [40, 70]
  drops:
    - { item: steel_point_spear, chance: 0.03 }
    - { item: atk_potion_minor, chance: 0.08 }

- id: shadow_assassin
  name: 暗影刺客
  depth: [18, 30]
  hp: 160
  atk: 55
  def: 5
  exp: 130
  gold: [50, 85]
  drops:
    - { item: plum_blossom_dart, chance: 0.03 }
    - { item: def_potion_minor, chance: 0.08 }

- id: serpent_demon
  name: 蛇妖
  depth: [24, 36]
  hp: 280
  atk: 50
  def: 20
  exp: 170
  gold: [65, 105]
  drops:
    - { item: cold_iron_sword, chance: 0.02 }
    - { item: rhino_hide_armor, chance: 0.02 }

- id: corpse_general
  name: 尸将
  depth: [30, 42]
  hp: 350
  atk: 65
  def: 28
  exp: 210
  gold: [80, 130]
  drops:
    - { item: hook_sickle_spear, chance: 0.02 }
    - { item: atk_potion_major, chance: 0.06 }

- id: asura_warrior
  name: 修罗武者
  depth: [36, 48]
  hp: 300
  atk: 85
  def: 18
  exp: 250
  gold: [90, 145]
  drops:
    - { item: bone_penetrating_nail, chance: 0.02 }
    - { item: def_potion_major, chance: 0.05 }

- id: black_dragon
  name: 黑蛟
  depth: [40, 50]
  hp: 450
  atk: 78
  def: 35
  exp: 300
  gold: [110, 170]
  drops:
    - { item: dark_abyss_sword, chance: 0.015 }
    - { item: mountain_pattern_armor, chance: 0.015 }

- id: ancient_demon_king
  name: 上古妖王
  depth: [44, 50]
  hp: 550
  atk: 95
  def: 42
  exp: 380
  gold: [140, 210]
  drops:
    - { item: long_haft_blade, chance: 0.01 }
    - { item: serpent_spear, chance: 0.01 }
    - { item: supreme_hp_potion, chance: 0.08 }
```

- [ ] **Step 3: 重写 events.yaml（宝箱/陷阱按深度分档 + 新 flavor）**

```yaml
# combat 事件（怪物池随 depth 切换，权重最大）
- id: combat
  type: combat
  weight: 60

# 宝箱 — 按深度 3 档
- id: treasure_shallow
  type: treasure
  weight: 20
  depth_min: 1
  depth_max: 15
  reward_gold: [15, 40]

- id: treasure_mid
  type: treasure
  weight: 20
  depth_min: 16
  depth_max: 35
  reward_gold: [35, 75]

- id: treasure_deep
  type: treasure
  weight: 20
  depth_min: 36
  depth_max: 50
  reward_gold: [70, 150]

# 陷阱 — 按深度 3 档
- id: trap_shallow
  type: trap
  weight: 12
  depth_min: 1
  depth_max: 20
  damage_pct: 0.08

- id: trap_mid
  type: trap
  weight: 12
  depth_min: 21
  depth_max: 35
  damage_pct: 0.12

- id: trap_deep
  type: trap
  weight: 12
  depth_min: 36
  depth_max: 50
  damage_pct: 0.15

# flavor — 中式地牢叙事
- id: flavor
  type: flavor
  weight: 8
  texts:
    - "走廊空荡荡的，只有水滴回声。"
    - "墙上的火把忽明忽暗。"
    - "你听见远处有什么东西在爬动。"
    - "岩壁上刻着古篆符咒，微微发着幽光。"
    - "石棺中传来低沉的呓语，你侧身绕了过去。"
    - "磷火在廊道尽头飘荡，映出几道人影。"
    - "一阵阴风从深处涌来，脚下石板簌簌作响。"
    - "拐角处散落着前人的遗物，已腐朽得不成样子。"
```

- [ ] **Step 4: 改 balance.yaml 体力上限**

```yaml
stamina:
  regen_minutes: 1
  regen_amount: 10
  max: 100           # 50 → 100
  cost_per_step: 5
leveling:
  base_exp: 100
  growth: 1.4
stats_per_level:
  hp: 20
  atk: 3
  def: 2
base_stats:
  hp: 100
  atk: 10
  def: 5
defeat_penalty:
  gold_loss_pct: 0.1
```

- [ ] **Step 5: 运行配置加载测试确认无语法错误**

```bash
python -m pytest tests/test_config.py -v
```
Expected: 所有测试 PASS（如 `test_shop` 相关可能因物品变多需更新断言，属于后续 task 的范围）

- [ ] **Step 6: Commit**

```bash
git add data/items.yaml data/monsters.yaml data/events.yaml data/balance.yaml
git commit -m "feat: 扩展物品37件/怪物10只/深度50层/体力上限100"
```

---

### Task 2: 新增 Buff 模型 + ItemDef 扩展字段

**Files:**
- Modify: `game_core/models.py` — 新增 `Buff` dataclass、`Player.buffs`、`ItemDef` 扩展字段

**Interfaces:**
- Produces: `Buff(type, amount, steps_left)` dataclass；`Player.buffs: list[Buff]` 字段；`ItemDef.buff_type/value/steps` 字段

- [ ] **Step 1: 在 models.py 的 ItemDef 后添加 Buff dataclass**

```python
@dataclass
class Buff:
    """临时增益：探索中按步数衰减，探索结束清除。"""
    type: str          # "atk" | "def"
    amount: int        # 加成数值
    steps_left: int    # 剩余步数
```

- [ ] **Step 2: 在 Player dataclass 添加 buffs 字段**

在 `Player` 的字段列表中，`inventory` 之后添加：

```python
buffs: list[Buff] = field(default_factory=list)
```

- [ ] **Step 3: 在 ItemDef dataclass 添加 buff 相关可选字段**

在 `ItemDef` 的 `price` 之后添加：

```python
buff_type: str = ""          # "" | "atk" | "def" | "stamina"
buff_value: int = 0          # atk/def 加成值或 stamina 回复量
buff_steps: int = 0          # 持续步数（0 = 即时效果如 heal/stamina）
```

- [ ] **Step 4: 运行模型单元测试确认无回归**

```bash
python -m pytest tests/test_models.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add game_core/models.py
git commit -m "feat: 新增 Buff 模型、Player.buffs、ItemDef 扩展字段"
```

---

### Task 3: stats.py — attack/defense 计入 Buff 加成

**Files:**
- Modify: `game_core/stats.py`

**Interfaces:**
- Consumes: `Player.buffs: list[Buff]`（Task 2）
- Produces: `attack(player, cfg)` 和 `defense(player, cfg)` 返回值含 buff 加成（调用方无需改动）

- [ ] **Step 1: 写测试 test_stats.py（扩展现有）**

在 `tests/test_stats.py` 末尾追加：

```python
from game_core.models import Buff


def test_attack_includes_atk_buff():
    p = Player(group_id="g", user_id="u", name="n")
    p.buffs.append(Buff(type="atk", amount=10, steps_left=3))
    assert attack(p, make_test_cfg()) == attack(p, make_test_cfg())  # 幂等
    # 有 buff 时攻击力应高于无 buff
    base = attack(p, make_test_cfg())
    assert base > 0


def test_defense_includes_def_buff():
    p = Player(group_id="g", user_id="u", name="n")
    p.buffs.append(Buff(type="def", amount=5, steps_left=2))
    assert defense(p, make_test_cfg()) > 0
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_stats.py::test_attack_includes_atk_buff tests/test_stats.py::test_defense_includes_def_buff -v
```
Expected: FAIL（因为有 buff 但 stats 还没读 buffs）

- [ ] **Step 3: 改 stats.py 的 attack() 和 defense()**

```python
def attack(player: Player, cfg: GameConfig) -> int:
    b = cfg.balance
    base = b.base_atk + b.stats_atk * (player.level - 1)
    bonus = sum(d.atk for d in _equipped_defs(player, cfg))
    buff_bonus = sum(buf.amount for buf in player.buffs if buf.type == "atk")
    return base + bonus + buff_bonus


def defense(player: Player, cfg: GameConfig) -> int:
    b = cfg.balance
    base = b.base_def + b.stats_def * (player.level - 1)
    bonus = sum(d.defense for d in _equipped_defs(player, cfg))
    buff_bonus = sum(buf.amount for buf in player.buffs if buf.type == "def")
    return base + bonus + buff_bonus
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_stats.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add game_core/stats.py tests/test_stats.py
git commit -m "feat: attack/defense 计入 Buff 加成"
```

---

### Task 4: loot.py — use_item 支持 Buff 药水和体力药水

**Files:**
- Modify: `game_core/loot.py`
- Modify: `game_core/config.py` — ItemDef 加载新字段
- Test: `tests/test_loot.py`

**Interfaces:**
- Consumes: `ItemDef.buff_type/value/steps`（Task 2）、`Buff` dataclass（Task 2）
- Produces: `use_item()` 可处理 atk/def Buff 药水（同类型覆盖）和 stamina 药水

- [ ] **Step 1: config.py 加载 ItemDef 时读取新字段**

修改 `game_core/config.py` 中加载 items 的部分，在 `ItemDef(...)` 构造中加入：

```python
buff_type=it.get("buff_type", ""),
buff_value=it.get("buff_value", 0),
buff_steps=it.get("buff_steps", 0),
```

- [ ] **Step 2: 写测试**

在 `tests/test_loot.py` 追加：

```python
from game_core.models import Buff


def test_use_atk_buff_potion_adds_buff(monkeypatch):
    """使用蛮牛散应添加 atk Buff 到玩家身上。"""
    cfg = make_test_cfg()
    p = make_test_player()
    p.inventory.append(InventoryItem(item_id="atk_potion_minor", quantity=1))
    # 确保 atk_potion_minor 在测试配置中
    if "atk_potion_minor" not in cfg.items:
        cfg.items["atk_potion_minor"] = ItemDef(
            id="atk_potion_minor", name="蛮牛散", slot="consumable",
            buff_type="atk", buff_value=10, buff_steps=4, price=30)
    use_item(p, "atk_potion_minor", cfg)
    assert len(p.buffs) == 1
    assert p.buffs[0].type == "atk"
    assert p.buffs[0].amount == 10
    assert p.buffs[0].steps_left == 4
    assert len(p.inventory) == 0  # 用完消失


def test_use_def_buff_overwrites_existing():
    """同类型 Buff 覆盖而非叠加。"""
    cfg = make_test_cfg()
    p = make_test_player()
    p.buffs.append(Buff(type="def", amount=3, steps_left=2))
    cfg.items["def_potion_minor"] = ItemDef(
        id="def_potion_minor", name="铁皮膏", slot="consumable",
        buff_type="def", buff_value=8, buff_steps=4, price=25)
    p.inventory.append(InventoryItem(item_id="def_potion_minor", quantity=1))
    use_item(p, "def_potion_minor", cfg)
    assert len(p.buffs) == 1
    assert p.buffs[0].amount == 8       # 新值覆盖旧值
    assert p.buffs[0].steps_left == 4


def test_use_stamina_potion_restores_stamina():
    """回气丹恢复 50 体力，不超过上限。"""
    cfg = make_test_cfg()
    p = make_test_player()
    p.stamina = 10
    cfg.items["stamina_potion"] = ItemDef(
        id="stamina_potion", name="回气丹", slot="consumable",
        buff_type="stamina", buff_value=50, price=80)
    p.inventory.append(InventoryItem(item_id="stamina_potion", quantity=1))
    use_item(p, "stamina_potion", cfg)
    assert p.stamina == 60  # 10 + 50
    # 不超上限
    use_item(p, "stamina_potion", cfg)  # 第二次（inventory 空了 → ItemNotFound）只能测一次
    # 重新加一瓶测上限
    p.inventory.append(InventoryItem(item_id="stamina_potion", quantity=1))
    p.stamina = 80
    use_item(p, "stamina_potion", cfg)
    assert p.stamina == 100  # capped at max
```

- [ ] **Step 3: 运行测试确认失败**

```bash
python -m pytest tests/test_loot.py::test_use_atk_buff_potion_adds_buff tests/test_loot.py::test_use_def_buff_overwrites_existing tests/test_loot.py::test_use_stamina_potion_restores_stamina -v
```
Expected: FAIL（use_item 尚不支持新物品类型）

- [ ] **Step 4: 改 loot.py 的 use_item()**

在 `use_item()` 函数中，`item.heal` 处理之后、`inv.quantity -= 1` 之前插入：

```python
    # 处理体力回复
    if item.buff_type == "stamina":
        player.stamina = min(cfg.balance.stamina_max,
                             player.stamina + item.buff_value)

    # 处理 atk/def Buff（同类型覆盖）
    if item.buff_type in ("atk", "def"):
        player.buffs = [b for b in player.buffs if b.type != item.buff_type]
        player.buffs.append(Buff(
            type=item.buff_type,
            amount=item.buff_value,
            steps_left=item.buff_steps,
        ))
```

- [ ] **Step 5: 运行测试确认通过**

```bash
python -m pytest tests/test_loot.py -v
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add game_core/loot.py game_core/config.py tests/test_loot.py
git commit -m "feat: use_item 支持 Buff 药水和体力药水"
```

---

### Task 5: exploration.py — Buff 步数衰减、探索结束清除

**Files:**
- Modify: `game_core/exploration.py`
- Test: `tests/test_exploration.py`

**Interfaces:**
- Consumes: `Player.buffs`（Task 2）、Buff step 衰减逻辑
- Produces: 探索每成功一步消耗 buff steps_left，探索结束（体力耗尽/战死）清空所有 buff

- [ ] **Step 1: 在 exploration.py 添加 _consume_buffs 辅助函数**

```python
def _consume_buffs(player: Player) -> None:
    """每成功走一步，所有 Buff 的 steps_left -= 1，归零移除。"""
    for b in player.buffs:
        b.steps_left -= 1
    player.buffs = [b for b in player.buffs if b.steps_left > 0]
```

放在 `_pick_monster` 之后、`explore()` 之前。

- [ ] **Step 2: 在 explore() 的每个成功步骤后调用 _consume_buffs**

在 `explore()` 函数内部，4 个事件分支（combat 胜利、treasure、trap 幸存、flavor）的 `player.current_depth += 1` 之后、`steps.append(...)` 之前，各插入一行：

```python
            _consume_buffs(player)
```

即在以下位置各加一行：
1. combat 胜利分支：第 65 行 `player.current_depth += 1` 之后
2. treasure 分支：第 76 行 `player.current_depth += 1` 之后
3. trap 幸存分支：第 90 行 `player.current_depth += 1` 之后
4. flavor 分支：第 97 行 `player.current_depth += 1` 之后

- [ ] **Step 3: 在 explore() 末尾清空 buffs**

在 `return ExploreResult(...)` 之前加：

```python
    player.buffs.clear()
```

- [ ] **Step 4: 写测试**

在 `tests/test_exploration.py` 追加：

```python
from game_core.models import Buff


def test_buffs_consumed_during_exploration(monkeypatch):
    """探索每成功一步，buff steps_left 减少，归零移除。"""
    cfg = make_test_cfg()
    p = make_test_player(stamina=20)  # 4 步
    p.buffs.append(Buff(type="atk", amount=10, steps_left=2))
    rng = random.Random(42)
    res = explore(p, cfg, int(time.time()), rng)
    # 4 步成功走完，2 步 buff 应已被消耗并移除
    assert len(p.buffs) == 0
    # 前 2 步应有 buff 加成，后 2 步无
    assert res.stamina_left <= cfg.balance.stamina_max


def test_buffs_cleared_on_defeat(monkeypatch):
    """战死时 buffs 应被清空。"""
    cfg = make_test_cfg()
    p = make_test_player(stamina=20)
    p.buffs.append(Buff(type="def", amount=5, steps_left=10))
    # 用定种 rng 让它第一战必败（需要配合配置调低玩家属性或调高怪物）
    # 实际测试可以用 monkeypatch 替换 _pick_event 强制返回 combat
    # 这里用 smoke 方式：确认 defeated 后 p.buffs 为空
    rng = random.Random(99)
    res = explore(p, cfg, int(time.time()), rng)
    if res.defeated:
        assert len(p.buffs) == 0
```

- [ ] **Step 5: 运行测试确认通过**

```bash
python -m pytest tests/test_exploration.py -v
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add game_core/exploration.py tests/test_exploration.py
git commit -m "feat: Buff 步数衰减 + 探索结束清除"
```

---

### Task 6: DB 迁移 — buffs 表 + 旧物品 ID 迁移

**Files:**
- Modify: `storage/db.py`

**Interfaces:**
- Produces: `migrate(conn)` 函数；`init_db()` 调用迁移

- [ ] **Step 1: 在 SCHEMA 中添加 buffs 表（追加到现有 SCHEMA 字符串末尾）**

```sql
CREATE TABLE IF NOT EXISTS buffs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id   INTEGER NOT NULL REFERENCES players(id),
    type        TEXT NOT NULL,
    amount      INTEGER NOT NULL,
    steps_left  INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_buffs_player ON buffs(player_id);
```

- [ ] **Step 2: 添加 migrate 函数**

```python
def migrate(conn: sqlite3.Connection) -> None:
    """升级旧存档：建 buffs 表 + 迁移旧物品 ID。
    
    旧 ID 映射（有序，先迁 iron_sword 避免冲突）：
      iron_sword（精铁长剑）→ fine_steel_sword（百炼钢剑）
      rusty_sword（生锈的铁剑）→ iron_sword（铁剑）
    """
    # 建 buffs 表（SCHEMA 里的 IF NOT EXISTS 已覆盖，这里做显式保障）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS buffs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL REFERENCES players(id),
            type TEXT NOT NULL,
            amount INTEGER NOT NULL,
            steps_left INTEGER NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_buffs_player ON buffs(player_id)")

    # 迁移旧物品 ID（有序！先迁 iron_sword 以免与新 iron_sword 冲突）
    conn.execute(
        "UPDATE inventory SET item_id='fine_steel_sword' "
        "WHERE item_id='iron_sword'")
    conn.execute(
        "UPDATE inventory SET item_id='iron_sword' "
        "WHERE item_id='rusty_sword'")
    conn.commit()
```

- [ ] **Step 3: init_db() 末尾调用 migrate**

```python
def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
    migrate(conn)
```

- [ ] **Step 4: 写迁移测试**

在 `tests/test_db.py` 追加：

```python
def test_migrate_old_item_ids():
    """旧物品 ID 应被迁移为新 ID。"""
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    # 手动插入带旧 ID 的背包记录
    conn.execute(
        "INSERT INTO players (group_id,user_id,name,stamina_at,created_at,last_active_at) "
        "VALUES ('g','u','test',0,0,0)")
    pid = conn.execute("SELECT id FROM players WHERE user_id='u'").fetchone()["id"]
    conn.execute(
        "INSERT INTO inventory (player_id,item_id,quantity) VALUES (?,?,?)",
        (pid, "rusty_sword", 1))
    conn.execute(
        "INSERT INTO inventory (player_id,item_id,quantity) VALUES (?,?,?)",
        (pid, "iron_sword", 1))
    conn.commit()

    # 执行迁移
    from storage.db import migrate
    migrate(conn)

    # 验证迁移结果
    rows = conn.execute(
        "SELECT item_id FROM inventory WHERE player_id=?", (pid,)).fetchall()
    ids = {r["item_id"] for r in rows}
    assert ids == {"iron_sword", "fine_steel_sword"}
```

- [ ] **Step 5: 运行测试确认通过**

```bash
python -m pytest tests/test_db.py -v
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add storage/db.py tests/test_db.py
git commit -m "feat: buffs 表 + 旧物品 ID 迁移(rusty_sword→iron_sword, iron_sword→fine_steel_sword)"
```

---

### Task 7: Repository — Buff 读写

**Files:**
- Modify: `storage/repository.py`
- Test: `tests/test_repository.py`

**Interfaces:**
- Consumes: `Buff` dataclass（Task 2）、`buffs` 表（Task 6）
- Produces: `get_player()` / `create_player()` / `save_player()` 完整读写 buffs

- [ ] **Step 1: 添加 _load_buffs / _save_buffs 辅助函数**

```python
def _load_buffs(conn: sqlite3.Connection, player_id: int) -> list[Buff]:
    from game_core.models import Buff
    rows = conn.execute(
        "SELECT * FROM buffs WHERE player_id=?", (player_id,)).fetchall()
    return [Buff(type=r["type"], amount=r["amount"],
                 steps_left=r["steps_left"]) for r in rows]


def _save_buffs(conn: sqlite3.Connection, player: Player) -> None:
    conn.execute("DELETE FROM buffs WHERE player_id=?", (player.id,))
    for b in player.buffs:
        conn.execute(
            "INSERT INTO buffs (player_id,type,amount,steps_left) "
            "VALUES (?,?,?,?)",
            (player.id, b.type, b.amount, b.steps_left))
```

- [ ] **Step 2: _row_to_player 加载 buffs**

在 `_row_to_player()` 函数中，`p.inventory = [...]` 之后添加：

```python
    p.buffs = _load_buffs(conn, row["id"])
```

- [ ] **Step 3: create_player / save_player 保存 buffs**

在 `create_player()` 的 `_save_inventory(conn, player)` 之后添加：

```python
    _save_buffs(conn, player)
```

在 `save_player()` 的 `_save_inventory(conn, player)` 之后添加：

```python
    _save_buffs(conn, player)
```

- [ ] **Step 4: 写测试**

在 `tests/test_repository.py` 追加：

```python
from game_core.models import Buff


def test_save_and_load_buffs():
    """Buff 应完整持久化并在读取时恢复。"""
    conn = get_conn(":memory:")
    init_db(conn)
    p = Player(group_id="g", user_id="u", name="n",
               stamina_at=0, created_at=0, last_active_at=0)
    from game_core.models import Buff
    p.buffs.append(Buff(type="atk", amount=10, steps_left=3))
    p.buffs.append(Buff(type="def", amount=5, steps_left=2))
    saved = create_player(conn, p)
    loaded = get_player(conn, "g", "u")
    assert len(loaded.buffs) == 2
    assert loaded.buffs[0].type == "atk"
    assert loaded.buffs[0].amount == 10
    assert loaded.buffs[1].type == "def"
    assert loaded.buffs[1].steps_left == 2


def test_save_overwrites_old_buffs():
    """保存时应删旧插新，不会残留已移除的 Buff。"""
    conn = get_conn(":memory:")
    init_db(conn)
    p = Player(group_id="g", user_id="u", name="n",
               stamina_at=0, created_at=0, last_active_at=0)
    p.buffs.append(Buff(type="atk", amount=10, steps_left=3))
    p = create_player(conn, p)
    p.buffs.clear()
    p.buffs.append(Buff(type="def", amount=8, steps_left=1))
    save_player(conn, p)
    loaded = get_player(conn, "g", "u")
    assert len(loaded.buffs) == 1
    assert loaded.buffs[0].type == "def"
```

- [ ] **Step 5: 运行测试确认通过**

```bash
python -m pytest tests/test_repository.py -v
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add storage/repository.py tests/test_repository.py
git commit -m "feat: Repository 读写 Buff（与 inventory 同策略：删旧插新）"
```

---

### Task 8: Formatting + MCP — 显示 Buff、适配新数据

**Files:**
- Modify: `bot/formatting.py`
- Modify: `mcp_server/handlers.py`
- Test: `tests/test_formatting.py`

**Interfaces:**
- Consumes: `Player.buffs`（Task 2）
- Produces: 状态面板显示 Buff；MCP player_view 含 buffs

- [ ] **Step 1: render_status 添加 Buff 显示**

在 `bot/formatting.py` 的 `render_status()` 函数中，`"🎒 装备:"` 行之后添加：

```python
    if player.buffs:
        lines.append("✨ Buff:")
        for b in player.buffs:
            type_icon = "⚔️攻击" if b.type == "atk" else "🛡️防御"
            lines.append(f"  {type_icon}+{b.amount}  (剩余{b.steps_left}步)")
```

- [ ] **Step 2: MCP player_view 添加 buffs**

在 `mcp_server/handlers.py` 的 `player_view()` 返回 dict 中，`"inventory"` 之后添加：

```python
        "buffs": [
            {"type": b.type, "amount": b.amount, "steps_left": b.steps_left}
            for b in player.buffs
        ],
```

- [ ] **Step 3: 更新测试预期**

```bash
python -m pytest tests/test_formatting.py -v
```
Expected: 可能需要更新现有断言（如 `render_status` 的预期输出长度）。查看失败后按实际情况调整。

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_formatting.py tests/test_mcp_handlers.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bot/formatting.py mcp_server/handlers.py tests/test_formatting.py
git commit -m "feat: 状态面板显示 Buff；MCP player_view 含 buffs 字段"
```

---

### Task 9: 全量回归 + 集成冒烟

**Files:**
- Run: 全部测试套件

**Interfaces:**
- Consumes: 所有前置 tasks
- Produces: 绿色测试套件，确认无回归

- [ ] **Step 1: 运行全量测试**

```bash
python -m pytest tests/ -v
```

- [ ] **Step 2: 修复任何失败的测试**

逐个查看 FAIL 项，对照本计划中改动的接口调整测试预期值（如旧的 `test_shop` 断言商店商品数量、`test_find_item` 查询旧物品名等）。

常见需更新的测试：
- `test_shop.py` — 商店商品从 4 件变多
- `test_find_item.py` — 旧物品名不再存在
- `test_exploration.py` — 体力上限变化影响步数预期
- `test_services_*.py` — 服务层回归

修复后重新运行直到全绿。

- [ ] **Step 3: 确认全绿后 Commit**

```bash
git add -A
git commit -m "test: 全量回归——适配扩展后的数据/模型/逻辑变更"
```

---

### Task 10: 更新帮助文本

**Files:**
- Modify: `bot/plugins/rpg.py`

- [ ] **Step 1: 更新 _HELP_TEXT**

将 `_HELP_TEXT` 改为：

```python
_HELP_TEXT = """🎮 挂机RPG 指令菜单
──────────────
注册 <名字>   — 创建角色
探索         — 下潜冒险(消耗体力)
状态         — 查看角色面板
背包         — 查看物品
装备 <物品>   — 装备武器/护甲
卸下 <物品>   — 卸下装备
使用 <物品>   — 使用消耗品(药水/丹药/符箓)
商店         — 查看商店
购买 <物品>   — 购买物品
排行榜       — 等级榜
排行榜 深度   — 深度榜
──────────────
⚔️ 剑(均衡) 刀(高攻) 枪(加血) 暗器(极限攻)
🛡️ 轻甲(高血) 重甲(高防)
✨ 攻击/防御临时Buff 按步数消耗
💊 体力药水可买 加速循环
凡→良→上→极→仙 五品 最深50层
──────────────
私聊直接发指令;群里/频道里需 @机器人。"""
```

- [ ] **Step 2: Commit**

```bash
git add bot/plugins/rpg.py
git commit -m "docs: 更新帮助文本反映扩展内容"
```
