# 设计文档:QQ 文字挂机探索 RPG 机器人

- **日期**:2026-06-18
- **状态**:已批准(待用户最终审阅)
- **作者**:与 Claude 协作 brainstorming 产出

---

## 1. 概述

一个运行在 QQ 群里的**文字挂机探索 RPG 机器人**。群成员 @机器人 发送中文指令,机器人被动返回相应消息。核心玩法循环:

> 离线时间积累「探索点(体力)」→ 玩家上线发 `探索`,一次性花光体力推进多步地牢探索 → 返回一长段冒险日志(战斗 / 宝箱 / 陷阱 / 叙事)→ 角色永久成长,潜得越来越深 → 群内排行榜攀比。

### 已确定的设计共识

| 维度 | 决策 |
|---|---|
| 玩法类型 | 文字探索 / 地牢流(探索 + 随机事件 + 叙事) |
| 挂机机制 | 时间 → 行动力(探索点),离线积累,上线一次性结算 |
| 角色持久性 | 永久成长,**无永久死亡**;战斗失败=「重伤回城」(损失少量金币 + 回到第 1 层) |
| 内容生成 | 数据驱动 + 随机(配置表 + 数值战斗公式) |
| 社交 | 群内排行榜(各玩各的,排名攀比) |
| 落地目标 | 先做本地 / 沙箱可跑通的完整 demo,不急上线真实大群 |
| 技术栈 | NoneBot2(Python)+ 官方 QQ 适配器 + SQLite + YAML 配置 |

### 重要平台约束

QQ 官方机器人自 2025-04-21 起**不能主动推送消息**,只能被动回复。因此"挂机"通过**离线体力按时间差现算**实现(玩家发指令时结算),而非后台定时推送。

---

## 2. 架构

采用**分层架构**:纯 Python「游戏核心」+ 薄「机器人适配层」。核心边界原则:

- `game_core/` **绝不 import nonebot**,不直接拼中文消息,只返回结构化结果对象 → 可脱离机器人独立单元测试。
- `bot/formatting.py` 是**唯一**负责"结果对象 → 中文文本"的地方。
- `storage/repository.py` 隔离"怎么存"与"游戏逻辑";`game_core` 只拿 `Player` 对象,不关心来源(测试时可塞内存假数据)。

```
玩家在 QQ 群 @机器人 发指令
        │
        ▼
┌─────────────────────────────┐
│  bot/  (NoneBot2 适配层,薄)  │  解析指令 → 调 core → 格式化中文回复
└─────────────────────────────┘
        │ 传入纯数据 / 调用纯函数
        ▼
┌─────────────────────────────┐
│  game_core/ (纯 Python 引擎)  │  不依赖 NoneBot,「数据进 → 结果出」
│   实体: 角色/怪物/物品          │  ← 单元测试主战场
│   系统: 探索/战斗/成长/排行     │
└─────────────────────────────┘
        │ 读写存档 / 读配置
        ▼
┌──────────────┐   ┌──────────────┐
│ storage/     │   │ data/ (配置)  │
│ SQLite 存档   │   │ 怪物/事件/掉落 │
└──────────────┘   └──────────────┘
```

### 目录结构

```
qq-idle-rpg/
├── bot/                      # NoneBot2 适配层(薄)
│   ├── __init__.py
│   ├── plugins/
│   │   ├── explore.py        # 探索、状态指令
│   │   ├── inventory.py      # 背包、装备指令
│   │   ├── shop.py           # 商店、购买指令
│   │   ├── ranking.py        # 排行榜指令
│   │   └── help.py           # 帮助、注册指令
│   └── formatting.py         # 结果对象 → 中文消息文本
│
├── game_core/                # 纯 Python 引擎(零 NoneBot 依赖)★测试核心
│   ├── models.py             # 数据类: Player, Monster, Item, ExploreResult...
│   ├── errors.py             # 领域异常: NotEnoughStamina, CharacterNotFound...
│   ├── stamina.py            # 离线体力(探索点)结算
│   ├── exploration.py        # 探索循环: 消耗体力→抽事件→产出日志
│   ├── combat.py             # 战斗数值结算
│   ├── progression.py        # 经验/升级/重伤回城惩罚
│   ├── loot.py               # 掉落与背包逻辑
│   ├── shop.py               # 商店购买逻辑
│   ├── ranking.py            # 排行榜计算
│   └── config.py             # 加载 + 校验 YAML 配置
│
├── data/                     # 配置表(改这里=改游戏内容)
│   ├── monsters.yaml
│   ├── events.yaml
│   ├── items.yaml
│   └── balance.yaml          # 数值: 体力速率/上限、升级曲线、惩罚等
│
├── storage/
│   ├── db.py                 # SQLite 连接 + 建表
│   └── repository.py         # 读写 Player / inventory 的仓储函数
│
├── tests/                    # pytest,主要测 game_core
│   ├── conftest.py           # 假仓储、假配置、定种 rng 等 fixture
│   ├── test_stamina.py
│   ├── test_combat.py
│   ├── test_exploration.py
│   ├── test_progression.py
│   ├── test_loot.py
│   ├── test_ranking.py
│   └── test_config.py
│
├── pyproject.toml            # 依赖: nonebot2, nonebot-adapter-qq, pyyaml, pytest
├── .env.dev                  # 沙箱机器人的 AppID/Secret/Token(不入库)
├── .gitignore
└── README.md
```

---

## 3. 数据模型

数据分两类:**存档**(玩家产生、会变 → SQLite)和**配置**(设计者编写、只读 → YAML)。

### 3.1 角色归属

**一个角色 = (群, 玩家) 组合**。映射 QQ 提供的 `群openid` + `群成员openid`。排行榜天然按本群范围;同一人在不同群是独立存档。

### 3.2 SQLite 存档表

```sql
-- 玩家角色(核心存档)
CREATE TABLE players (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id        TEXT NOT NULL,         -- QQ 群 openid
    user_id         TEXT NOT NULL,         -- QQ 群成员 openid
    name            TEXT NOT NULL,         -- 角色名(注册时取)
    level           INTEGER NOT NULL DEFAULT 1,
    exp             INTEGER NOT NULL DEFAULT 0,
    gold            INTEGER NOT NULL DEFAULT 0,
    stamina         INTEGER NOT NULL DEFAULT 0,   -- 当前探索点
    stamina_at      INTEGER NOT NULL,             -- 上次结算体力的时间戳(离线积累用)
    current_hp      INTEGER NOT NULL,             -- 当前血量(跨下潜累计)
    current_depth   INTEGER NOT NULL DEFAULT 1,   -- 当前所在层
    max_depth       INTEGER NOT NULL DEFAULT 1,   -- 历史最深层(排行榜用,永不回退)
    created_at      INTEGER NOT NULL,
    last_active_at  INTEGER NOT NULL,
    UNIQUE(group_id, user_id)              -- 一群一人一角色
);

-- 背包 / 装备(装备 = equipped=1 的物品)
CREATE TABLE inventory (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id   INTEGER NOT NULL REFERENCES players(id),
    item_id     TEXT NOT NULL,             -- 指向 items.yaml 的 id
    quantity    INTEGER NOT NULL DEFAULT 1,
    equipped    INTEGER NOT NULL DEFAULT 0
);
```

> **派生属性不存,实时算**:`hp_max`、`atk`、`def`、`战力` 都由「等级 + 已装备物品」计算得出,避免存档不一致。

### 3.3 配置表(YAML)

**`balance.yaml`** — 全局数值旋钮:
```yaml
stamina:
  regen_minutes: 5      # 每 5 分钟回 1 点探索点
  max: 50               # 上限
  cost_per_step: 5      # 每步探索消耗 → 满体力可走 10 步
leveling:
  base_exp: 100         # 1→2 级所需经验
  growth: 1.4           # 每级经验需求 ×1.4
stats_per_level:        # 升级自动加的属性
  hp: 20
  atk: 3
  def: 2
base_stats:             # 1 级基础属性
  hp: 100
  atk: 10
  def: 5
defeat_penalty:
  gold_loss_pct: 0.1    # 重伤回城损失 10% 金币
```

**`monsters.yaml`**:
```yaml
- id: slime
  name: 史莱姆
  depth: [1, 5]         # 出现层数范围
  hp: 30
  atk: 5
  def: 1
  exp: 15
  gold: [3, 8]          # 掉落金币区间
  drops:                # 概率掉落
    - { item: rusty_sword, chance: 0.05 }
```

**`events.yaml`** — 探索每一步按权重抽:
```yaml
- id: combat       # 战斗:从 monsters 按当前层抽一只
  type: combat
  weight: 60
- id: treasure     # 宝箱
  type: treasure
  weight: 20
  reward: { gold: [10, 30] }
- id: trap         # 陷阱:掉血
  type: trap
  weight: 10
  damage_pct: 0.1
- id: flavor       # 叙事描述
  type: flavor
  weight: 10
  texts: ["走廊空荡荡的,只有水滴回声。", "墙上的火把忽明忽暗。"]
```

**`items.yaml`**:
```yaml
- id: rusty_sword
  name: 生锈的铁剑
  slot: weapon       # weapon / armor / consumable
  atk: 5
  rarity: common
  price: 50          # 有 price 即可在商店出售
- id: hp_potion
  name: 治疗药水
  slot: consumable
  heal: 50
  price: 20
```

### 3.4 核心结果对象(战斗/探索算完返回,不含中文排版)

```python
@dataclass
class StepLog:          # 探索的一步
    kind: str           # "combat" | "treasure" | "trap" | "flavor"
    depth: int
    monster: str | None = None
    won: bool | None = None
    rounds: int = 0
    gold: int = 0
    exp: int = 0
    items: list[str] = field(default_factory=list)
    hp_after: int = 0
    text: str = ""      # flavor 文案等

@dataclass
class ExploreResult:    # 一次"探索"指令的完整结算
    steps: list[StepLog]
    total_gold: int
    total_exp: int
    items_gained: list[str]
    level_ups: int
    defeated: bool       # 是否重伤回城
    stamina_left: int
    depth_before: int
    depth_after: int
    hp_after: int
    hp_max: int
```

---

## 4. 核心系统算法

### 4.1 离线体力结算(不用后台定时器)

玩家每次发指令时按时间差现算。纯函数,`now` 注入便于测试:

```python
def settle_stamina(player, now, cfg):
    elapsed_min = (now - player.stamina_at) // 60
    regen = elapsed_min // cfg.regen_minutes      # 回了几点
    if regen > 0:
        player.stamina = min(cfg.max, player.stamina + regen)
        # 时间戳只推进"已兑现"的分钟,余数留到下次,不浪费
        player.stamina_at += regen * cfg.regen_minutes * 60
    if player.stamina >= cfg.max:                 # 满了就把时间戳拉到现在
        player.stamina = cfg.max
        player.stamina_at = now
```

### 4.2 探索循环

```
先 settle_stamina(player)
steps = []
while player.stamina >= cost_per_step:
    player.stamina -= cost_per_step
    event = 按权重和当前层抽一个事件(events.yaml)
    分支:
      combat   → 按 current_depth 抽一只怪 → resolve_combat()
                   赢:拿 exp/金币/掉落,current_depth += 1
                   输:重伤回城(见 4.4),break
      treasure → 拿金币,current_depth += 1
      trap     → current_hp -= hp_max × damage_pct;若 ≤0 → 重伤回城,break
      flavor   → 纯叙事,current_depth += 1
更新 max_depth = max(max_depth, current_depth)
返回 ExploreResult(steps, 汇总)
```

**层数逻辑**:每成功一步 `current_depth += 1`,越深怪越强;`max_depth` 记录历史最深(排行榜用,永不回退)。角色靠永久变强,一次比一次潜得深。

### 4.3 战斗结算(自动、回合制、数值驱动)

```python
def resolve_combat(player_stats, monster, rng):
    mhp = monster.hp
    for r in range(1, 51):                         # 上限 50 回合防死循环
        dmg = max(1, player_stats.atk - monster.def) * rng.uniform(0.9, 1.1)
        mhp -= dmg
        if mhp <= 0:
            return CombatResult(won=True, rounds=r, ...)
        dmg = max(1, monster.atk - player_stats.def) * rng.uniform(0.9, 1.1)
        player_stats.current_hp -= dmg
        if player_stats.current_hp <= 0:
            return CombatResult(won=False, rounds=r, ...)
    return CombatResult(won=False, reason="缠斗过久撤退")
```

### 4.4 成长 & 重伤回城

```python
def grant_exp(player, amount, cfg):
    player.exp += amount
    while player.exp >= exp_need(player.level, cfg):   # base_exp * growth^(lv-1)
        player.exp -= exp_need(player.level, cfg)
        player.level += 1
        # 升级:属性按 stats_per_level 增长,并回满血作为奖励

def apply_defeat(player, cfg):                          # 重伤回城
    player.gold -= int(player.gold * cfg.gold_loss_pct) # 损失 10% 金币
    player.current_depth = 1                            # 回到第 1 层(max_depth 保留)
    player.current_hp = hp_max(player)                  # 满血
```

**派生属性公式**:
```
hp_max = base.hp + stats_per_level.hp*(lv-1) + 已装备护甲.hp
atk    = base.atk + stats_per_level.atk*(lv-1) + 已装备武器.atk
def    = base.def + stats_per_level.def*(lv-1) + 已装备.def
战力   = atk*2 + def*2 + hp_max*0.5
```

### 4.5 排行榜

v1 用存档已有列直接排,纯 SQL:
```sql
-- 默认等级榜(同级比最深层)
SELECT name, level, max_depth FROM players
WHERE group_id = ? ORDER BY level DESC, max_depth DESC LIMIT 10;
```
- `排行榜` → 等级榜
- `排行榜 深度` → 最深层榜
- **战力榜**(需读装备实时算)作为 v2 扩展:取前 20 名在 Python 里算战力再排。

---

## 5. 指令集

群里玩家 **@机器人 + 关键词** 触发,带同义词容错。

| 指令 | 同义词 | 作用 | 耗体力 |
|---|---|---|---|
| `注册 <角色名>` | `创建` | 首次创建角色 | — |
| `探索` | `下潜`、`冒险` | **核心**:花光体力,返回冒险日志 | ✅ |
| `状态` | `我`、`角色` | 看等级/经验/HP/体力/金币/层数/战力 | ❌ |
| `背包` | `物品` | 列出拥有的物品 | ❌ |
| `装备 <物品>` | — | 穿上武器/护甲 | ❌ |
| `卸下 <物品>` | — | 卸下装备 | ❌ |
| `使用 <物品>` | — | 用消耗品(如药水回血) | ❌ |
| `商店` | — | 看在售物品 + 价格 | ❌ |
| `购买 <物品>` | `买` | 花金币购买 | ❌ |
| `排行榜 [深度]` | `排名` | 本群等级榜 / 深度榜 | ❌ |
| `帮助` | `菜单`、`?` | 指令说明 | ❌ |

**经济闭环**:探索赚金币 → 商店买更强装备 → 潜得更深 → 赚更多。商店商品 = `items.yaml` 中标了 `price` 的条目。

### 示例输出:`探索`

```
🗡️ 【勇者·小明】的下潜 (第3层 → 第6层)

第3层 ⚔️ 史莱姆 → 2回合击败  +15exp +6金币
第4层 📦 蒙尘的木箱  +24金币
第5层 ⚔️ 哥布林 → 4回合击败,-12HP  +28exp +11金币
       ✨ 掉落【生锈的铁剑】
第6层 ⚠️ 踩中陷阱  -15HP

──────────────
本次合计:+43exp  +41金币  获得1件装备
❤️ HP 73/120   ⚡ 体力 0/50
📊 升级到 Lv.4!   🏆 最深抵达 第6层
💤 体力耗尽,约4小时10分后回满,届时再来下潜
```

### 示例输出:`状态`

```
🛡️ 勇者·小明  Lv.4  (本群)
经验 38/220
❤️ HP 73/120   ⚡ 体力 12/50
⚔️ 攻击 18   🛡️ 防御 9   💪 战力 156
💰 金币 312   🏆 最深 第6层
🎒 装备:生锈的铁剑 / —
```

### 交互细节
- 未注册发 `探索` → `你还没有角色,先发「注册 你的角色名」吧~`
- 体力不足 → `体力不够啦(需 5,当前 3),约 10 分钟后可再探索。`
- 角色名做长度 / 敏感词 / 同群重名校验。
- 单步只输出一行摘要,控制消息长度。

---

## 6. 错误处理

**原则:异常不出群,玩家只看到友好提示。**

- `game_core` 用领域异常表达业务错误(`NotEnoughStamina`、`CharacterNotFound`、`DuplicateName`、`ItemNotFound` 等),不自己拼中文。
- `bot` 层每个处理器统一 `try/except`:
  - `GameError` → 翻译成友好中文。
  - 未预期异常 → **不把堆栈发到群**,服务器端 `logger.exception` 记日志 + 回 `"⚠️ 出了点小问题,已记录,稍后再试~"`。
- **数据一致性**:一次 `探索` 改 player + inventory,用 **SQLite 事务**包裹,要么整次提交要么回滚。
- **同玩家并发**:按 `player_id` 加 `asyncio` 锁串行处理,避免双花体力。
- **配置启动校验**:加载 YAML 后 `validate_config()` 检查权重为正、`drops`/商店引用的 item 存在等,**配置写错在启动时即报错**。
- **可测试性**:`now` 与 `rng` 作为参数注入 `game_core`,测试可传固定值复现结果。

---

## 7. 测试策略

用 **pytest**,主战场 `game_core`(假仓储 + 假配置 + 定种 rng,无需起机器人)。

| 测试文件 | 覆盖点 |
|---|---|
| `test_stamina.py` | 离线 0/部分/超量时间的回复、上限封顶、余数不丢 |
| `test_combat.py` | 定种随机下胜/负、伤害公式边界(攻≤防至少 1 伤)、50 回合上限 |
| `test_exploration.py` | 层数递进、体力耗尽停止、战败回城+回第1层+max_depth保留 |
| `test_progression.py` | 一次大经验跨多级、升级曲线、重伤扣 10% 金币 |
| `test_loot.py` | 掉落概率、背包堆叠、装备/卸下、战力重算 |
| `test_ranking.py` | 排序正确、同级比深度、只算本群(群隔离) |
| `test_config.py` | 加载真实 YAML 跑完整探索,抓配置引用错误 |

- `bot` 层薄 → 主要测 `formatting`(给定结果对象,断言中文含关键字段)和指令解析(同义词、缺参)。
- NoneBot 适配层可用 `nonebug` 轻量冒烟测试(可选),最终在沙箱频道人工验收。
- **开发方式**:核心系统先写测试再写实现(TDD)。

---

## 8. 范围与非目标(YAGNI)

**v1 包含**:注册、离线体力、探索循环、数值战斗、成长/重伤回城、背包/装备、商店、等级榜/深度榜、帮助。

**明确不做(留待 v2+)**:
- 主动推送 / 定时播报(平台不支持)
- PvP / 切磋、组队探索、交易行、公会(深度多人)
- 手写剧情主线(先纯数据驱动随机)
- 战力榜(v2,需实时算装备)
- 真实大群上线 / 过审 / 常驻服务器部署(先本地+沙箱)
- 完整 ECS 引擎(过度设计)
