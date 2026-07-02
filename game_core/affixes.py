from __future__ import annotations

import json
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class AffixTemplate:
    name: str
    effects: dict[str, tuple[float, float]]


WEAPON_AFFIXES = [
    AffixTemplate("锋锐", {"atk_pct": (0.08, 0.20)}),
    AffixTemplate("嗜血", {"lifesteal_pct": (0.05, 0.15)}),
    AffixTemplate("破甲", {"atk_pct": (0.05, 0.12)}),
    AffixTemplate("钝刃", {"atk_pct": (-0.15, -0.05)}),
    AffixTemplate("沉重", {"def_pct": (-0.12, -0.04)}),
    AffixTemplate("狂战", {"atk_pct": (0.10, 0.20), "def_pct": (-0.15, -0.05)}),
    AffixTemplate("贪婪", {"gold_pct": (0.10, 0.20), "atk_pct": (-0.12, -0.05)}),
]

ARMOR_AFFIXES = [
    AffixTemplate("坚壁", {"def_pct": (0.08, 0.20)}),
    AffixTemplate("厚血", {"hp_pct": (0.08, 0.20)}),
    AffixTemplate("轻盈", {"def_pct": (0.05, 0.12), "hp_pct": (0.05, 0.12)}),
    AffixTemplate("破损", {"def_pct": (-0.15, -0.05)}),
    AffixTemplate("笨重", {"atk_pct": (-0.12, -0.04)}),
    AffixTemplate("重装", {"def_pct": (0.10, 0.20), "atk_pct": (-0.15, -0.05)}),
    AffixTemplate("血甲", {"hp_pct": (0.10, 0.20), "def_pct": (-0.12, -0.05)}),
]

STAT_LABELS = {
    "atk_pct": "攻击",
    "def_pct": "防御",
    "hp_pct": "生命",
    "gold_pct": "金币",
    "lifesteal_pct": "吸血",
}


def roll_affix(slot: str, rng: random.Random | None = None) -> str:
    rng = rng or random.Random()
    pool = WEAPON_AFFIXES if slot == "weapon" else ARMOR_AFFIXES
    template = rng.choice(pool)
    effects = {
        stat: round(rng.uniform(lo, hi), 2)
        for stat, (lo, hi) in template.effects.items()
    }
    return json.dumps({"name": template.name, "effects": effects}, ensure_ascii=False, sort_keys=True)


def parse_affix(affix: str | None) -> dict:
    if not affix:
        return {}
    try:
        data = json.loads(affix)
    except (TypeError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    effects = data.get("effects")
    if not isinstance(effects, dict):
        return {}
    return data


def modifiers(affix: str | None) -> dict[str, float]:
    data = parse_affix(affix)
    return {k: float(v) for k, v in data.get("effects", {}).items()}


def modifier_total(affixes, stat: str) -> float:
    return sum(modifiers(affix).get(stat, 0.0) for affix in affixes)


def format_affix(affix: str | None) -> str:
    data = parse_affix(affix)
    if not data:
        return ""
    parts = []
    for stat, value in data.get("effects", {}).items():
        sign = "+" if value >= 0 else ""
        parts.append(f"{STAT_LABELS.get(stat, stat)}{sign}{int(round(value * 100))}%")
    return f"{data.get('name', '词条')}(" + " ".join(parts) + ")"
