from __future__ import annotations

import random
from dataclasses import dataclass, field

from game_core.models import GameConfig, Player, WorldBossDef
from game_core import stats

WORLD_BOSS_STAMINA_COST = 50
WORLD_BOSS_GOLD_LOSS_PCT = 0.05
WORLD_BOSS_MAX_ROUNDS = 300

CONSUMABLE_REWARD_POOL = [
    "hp_potion",
    "greater_hp_potion",
    "supreme_hp_potion",
    "atk_potion_major",
    "def_potion_major",
    "refined_iron",
    "black_iron",
    "star_meteorite",
    "divine_forge_crystal",
]

MATERIAL_REWARD_POOL = [
    "refined_iron",
    "black_iron",
    "star_meteorite",
    "divine_forge_crystal",
]

MID_HIGH_GEAR_POOL = [
    "thunder_soul_sword",
    "cloud_splitter_blade",
    "meteor_halberd",
    "soul_lock_nails",
    "thunder_plate",
    "phoenix_feather_armor",
]

HIGH_CONTRIBUTION_GEAR_POOL = [
    "void_cleaver_sword",
    "blood_sea_blade",
    "heaven_river_spear",
    "nether_blossom_dart",
    "mirage_armor",
    "basalt_king_plate",
]

VERY_RARE_GEAR_POOL = [
    "skyfall_sword",
    "king_hell_blade",
    "nine_suns_spear",
    "silent_ending_needles",
    "galaxy_robe",
    "heaven_fortress_plate",
]


@dataclass(frozen=True)
class WorldBossState:
    hp_current: int
    atk: int
    defense: int


@dataclass(frozen=True)
class WorldBossAttackSimulation:
    damage: int
    rounds: int
    player_hp_after: int
    player_defeated: bool
    boss_defeated: bool


@dataclass(frozen=True)
class WorldBossDropChances:
    normal_gear: float
    rare_gear: float
    mythic_or_high_tier: float


@dataclass(frozen=True)
class WorldBossReward:
    gold: int
    consumables: list[tuple[str, int]] = field(default_factory=list)
    gear_item_id: str = ""


def _hit(attacker_atk: int, defender_def: int, rng: random.Random) -> int:
    raw = max(1, attacker_atk - defender_def)
    return max(1, round(raw * rng.uniform(0.9, 1.1)))


def simulate_world_boss_attack(
    player: Player,
    boss: WorldBossState,
    cfg: GameConfig,
    rng: random.Random,
) -> WorldBossAttackSimulation:
    player_atk = stats.attack(player, cfg)
    player_def = stats.defense(player, cfg)
    player_hp_max = stats.hp_max(player, cfg)
    lifesteal = stats.lifesteal(player, cfg)
    hp = player.current_hp if player.current_hp > 0 else player_hp_max
    boss_hp = boss.hp_current
    total_damage = 0

    for round_no in range(1, WORLD_BOSS_MAX_ROUNDS + 1):
        damage = _hit(player_atk, boss.defense, rng)
        boss_hp -= damage
        total_damage += damage
        if lifesteal > 0:
            hp = min(player_hp_max, hp + max(1, int(damage * lifesteal)))
        if boss_hp <= 0:
            return WorldBossAttackSimulation(
                damage=total_damage,
                rounds=round_no,
                player_hp_after=hp,
                player_defeated=False,
                boss_defeated=True,
            )

        hp -= _hit(boss.atk, player_def, rng)
        if hp <= 0:
            return WorldBossAttackSimulation(
                damage=total_damage,
                rounds=round_no,
                player_hp_after=hp,
                player_defeated=True,
                boss_defeated=False,
            )

    return WorldBossAttackSimulation(
        damage=total_damage,
        rounds=WORLD_BOSS_MAX_ROUNDS,
        player_hp_after=hp,
        player_defeated=hp <= 0,
        boss_defeated=False,
    )


def reward_drop_chances(damage_percent: float) -> WorldBossDropChances:
    pct = max(0.0, min(1.0, damage_percent))
    return WorldBossDropChances(
        normal_gear=0.20 + pct * 0.80,
        rare_gear=0.08 + pct * 0.60,
        mythic_or_high_tier=0.02 + pct * 0.20,
    )


def _existing_items(cfg: GameConfig, item_ids: list[str]) -> list[str]:
    return [item_id for item_id in item_ids if item_id in cfg.items]


def _add_weights(base: dict[str, int], increments: dict[str, int]) -> None:
    for item_id, value in increments.items():
        base[item_id] = max(0, base.get(item_id, 0) + int(value))


def growth_material_weights(
    player: Player,
    boss_def: WorldBossDef | None = None,
) -> dict[str, int]:
    depth = max(1, player.max_depth)
    weights = {item_id: 0 for item_id in MATERIAL_REWARD_POOL}

    if depth <= 40:
        _add_weights(weights, {"refined_iron": 4, "black_iron": 1})
        target_enhance = 4
        target_star = 1
    elif depth <= 70:
        _add_weights(weights, {"refined_iron": 3, "black_iron": 4, "star_meteorite": 1})
        target_enhance = 8
        target_star = 2
    elif depth <= 100:
        _add_weights(weights, {"black_iron": 3, "star_meteorite": 3, "divine_forge_crystal": 1})
        target_enhance = 12
        target_star = 3
    else:
        _add_weights(weights, {"star_meteorite": 4, "divine_forge_crystal": 2})
        target_enhance = 16
        target_star = 4

    equipped = [inv for inv in player.inventory if inv.equipped]
    if equipped:
        avg_enhance = sum(inv.enhance_level for inv in equipped) / len(equipped)
        avg_star = sum(inv.star_level for inv in equipped) / len(equipped)
        if avg_enhance < target_enhance:
            if depth <= 40:
                _add_weights(weights, {"refined_iron": 3})
            elif depth <= 70:
                _add_weights(weights, {"refined_iron": 2, "black_iron": 2})
            elif depth <= 100:
                _add_weights(weights, {"black_iron": 2, "star_meteorite": 2})
            else:
                _add_weights(weights, {"star_meteorite": 3, "divine_forge_crystal": 1})
        if avg_star < target_star:
            if depth <= 70:
                _add_weights(weights, {"black_iron": 2})
            elif depth <= 100:
                _add_weights(weights, {"star_meteorite": 2, "divine_forge_crystal": 1})
            else:
                _add_weights(weights, {"divine_forge_crystal": 2})

    if boss_def is not None:
        _add_weights(weights, boss_def.material_bias)

    return {item_id: weight for item_id, weight in weights.items() if weight > 0}


def _weighted_material_choice(
    cfg: GameConfig,
    rng: random.Random,
    material_weights: dict[str, int] | None,
) -> str:
    weights = {
        item_id: weight
        for item_id, weight in (material_weights or {}).items()
        if weight > 0 and item_id in cfg.items
    }
    if not weights:
        fallback = _existing_items(cfg, MATERIAL_REWARD_POOL)
        return rng.choice(fallback) if fallback else ""
    total = sum(weights.values())
    roll = rng.randint(1, total)
    running = 0
    for item_id, weight in weights.items():
        running += weight
        if roll <= running:
            return item_id
    return next(iter(weights))


def roll_world_boss_rewards(
    damage_percent: float,
    player_level: int,
    active_player_count: int,
    cfg: GameConfig,
    rng: random.Random,
    reward_multiplier: float = 1.0,
    min_gold: int = 0,
    material_weights: dict[str, int] | None = None,
    extra_material_count: int = 0,
) -> WorldBossReward:
    pct = max(0.0, min(1.0, damage_percent))
    base_gold = 800 + player_level * 30
    boss_gold_pool = 20_000 + max(1, active_player_count) * 5_000
    gold = max(int(min_gold), int((base_gold + boss_gold_pool * pct) * reward_multiplier))

    consumable_pool = _existing_items(cfg, CONSUMABLE_REWARD_POOL)
    consumables: list[tuple[str, int]] = []
    if consumable_pool:
        for _ in range(rng.randint(1, 3)):
            consumables.append((rng.choice(consumable_pool), 1))
    for _ in range(max(0, int(extra_material_count))):
        item_id = _weighted_material_choice(cfg, rng, material_weights)
        if item_id:
            consumables.append((item_id, 1))

    chances = reward_drop_chances(pct)
    gear_item_id = ""
    if rng.random() < chances.mythic_or_high_tier:
        pool = _existing_items(cfg, VERY_RARE_GEAR_POOL)
        gear_item_id = rng.choice(pool) if pool else ""
    elif rng.random() < chances.rare_gear:
        pool = _existing_items(cfg, HIGH_CONTRIBUTION_GEAR_POOL)
        gear_item_id = rng.choice(pool) if pool else ""
    elif rng.random() < chances.normal_gear:
        pool = _existing_items(cfg, MID_HIGH_GEAR_POOL)
        gear_item_id = rng.choice(pool) if pool else ""

    return WorldBossReward(
        gold=gold,
        consumables=consumables,
        gear_item_id=gear_item_id,
    )
