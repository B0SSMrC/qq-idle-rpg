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
