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
    buff_type: str = ""             # "" | "atk" | "def" | "stamina"
    buff_value: int = 0             # atk/def 加成值或 stamina 回复量
    buff_steps: int = 0             # 持续步数（0 = 即时效果如 heal/stamina）


@dataclass
class Buff:
    """临时增益：探索中按步数衰减，探索结束清除。"""
    type: str          # "atk" | "def"
    amount: int        # 加成数值
    steps_left: int    # 剩余步数


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
    stamina_regen_amount: int = 1   # 每次结算回多少点(默认1=旧行为)


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
    affix: str = ""
    source: str = ""


@dataclass
class SoldItem:
    item_id: str
    name: str
    quantity: int
    unit_price: int
    total_price: int


@dataclass
class SellResult:
    sold_items: list[SoldItem] = field(default_factory=list)
    total_gold: int = 0


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
    stamina_refill_window_start: int = 0
    stamina_refill_window_amount: int = 0
    overdrive_until: int = 0
    created_at: int = 0
    last_active_at: int = 0
    inventory: list[InventoryItem] = field(default_factory=list)
    buffs: list[Buff] = field(default_factory=list)
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
