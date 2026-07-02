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
