import random
from pathlib import Path

from game_core.config import load_config
from game_core.models import InventoryItem, Player
from game_core.world_boss import (
    WORLD_BOSS_GOLD_LOSS_PCT,
    WORLD_BOSS_STAMINA_COST,
    WorldBossState,
    reward_drop_chances,
    roll_world_boss_rewards,
    simulate_world_boss_attack,
)
from storage import world_boss_repo


CFG = load_config(Path("data"))


def test_world_boss_constants_match_design():
    assert WORLD_BOSS_STAMINA_COST == 50
    assert WORLD_BOSS_GOLD_LOSS_PCT == 0.05


def test_simulate_world_boss_attack_until_player_defeat():
    player = Player(
        group_id="g",
        user_id="u",
        name="cxh",
        level=20,
        current_hp=300,
    )
    player.inventory = [
        InventoryItem(item_id="iron_sword", equipped=True),
        InventoryItem(item_id="cloth_armor", equipped=True),
    ]
    boss = WorldBossState(hp_current=120000, atk=360, defense=180)

    result = simulate_world_boss_attack(player, boss, CFG, random.Random(1))

    assert result.damage > 0
    assert result.rounds >= 1
    assert result.player_defeated is True
    assert result.boss_defeated is False
    assert result.player_hp_after <= 0


def test_simulate_world_boss_attack_can_defeat_low_hp_boss():
    player = Player(
        group_id="g",
        user_id="u",
        name="cxh",
        level=100,
        current_hp=5000,
    )
    player.inventory = [
        InventoryItem(item_id="silent_ending_needles", equipped=True),
        InventoryItem(item_id="heaven_fortress_plate", equipped=True),
    ]
    boss = WorldBossState(hp_current=10, atk=1, defense=1)

    result = simulate_world_boss_attack(player, boss, CFG, random.Random(2))

    assert result.damage >= 10
    assert result.boss_defeated is True
    assert result.player_defeated is False


def test_reward_drop_chances_increase_with_damage_percent():
    low = reward_drop_chances(0.05)
    high = reward_drop_chances(0.50)

    assert high.rare_gear > low.rare_gear
    assert low.rare_gear > 0.03


def test_roll_world_boss_rewards_scales_gold_with_damage_percent():
    low = roll_world_boss_rewards(0.05, player_level=10, active_player_count=4,
                                  cfg=CFG, rng=random.Random(1))
    high = roll_world_boss_rewards(0.50, player_level=10, active_player_count=4,
                                   cfg=CFG, rng=random.Random(1))

    assert high.gold > low.gold
    assert len(high.consumables) >= 1


def test_roll_world_boss_rewards_applies_reward_multiplier():
    normal = roll_world_boss_rewards(
        0.25, player_level=30, active_player_count=3, cfg=CFG,
        rng=random.Random(1), reward_multiplier=1.0
    )
    boosted = roll_world_boss_rewards(
        0.25, player_level=30, active_player_count=3, cfg=CFG,
        rng=random.Random(1), reward_multiplier=2.0
    )

    assert boosted.gold == normal.gold * 2


def test_world_boss_rewards_can_include_upgrade_materials():
    seen_material = False
    for seed in range(100):
        reward = roll_world_boss_rewards(
            0.5,
            player_level=30,
            active_player_count=3,
            cfg=CFG,
            rng=random.Random(seed),
        )
        if any(
            item_id in {"star_meteorite", "divine_forge_crystal"}
            for item_id, _ in reward.consumables
        ):
            seen_material = True
            break

    assert seen_material


def _current_cxh_player():
    player = Player(
        group_id="g",
        user_id="2474424608",
        name="cxh",
        level=18,
        current_hp=1016,
    )
    player.inventory = [
        InventoryItem(
            item_id="phoenix_feather_armor",
            equipped=True,
            affix='{"name":"轻盈","effects":{"def_pct":0.11,"hp_pct":0.12}}',
        ),
        InventoryItem(
            item_id="thunderclap_blade",
            equipped=True,
            affix='{"name":"锋锐","effects":{"atk_pct":0.13}}',
        ),
    ]
    return player


def _current_crazy_player():
    player = Player(
        group_id="g",
        user_id="2082242067",
        name="Crazy",
        level=18,
        current_hp=818,
    )
    player.inventory = [
        InventoryItem(
            item_id="thunder_plate",
            equipped=True,
            affix='{"name":"厚血","effects":{"hp_pct":0.19}}',
        ),
        InventoryItem(
            item_id="soul_lock_nails",
            equipped=True,
            affix='{"name":"锋锐","effects":{"atk_pct":0.10}}',
        ),
    ]
    return player


def test_current_players_attack_about_ten_percent_of_two_player_world_boss():
    boss_hp = (
        world_boss_repo.WORLD_BOSS_BASE_HP
        + world_boss_repo.WORLD_BOSS_HP_PER_ACTIVE_PLAYER * 2
    )
    boss = WorldBossState(
        hp_current=boss_hp,
        atk=world_boss_repo.WORLD_BOSS_ATK,
        defense=world_boss_repo.WORLD_BOSS_DEF,
    )

    for player in [_current_cxh_player(), _current_crazy_player()]:
        ratios = [
            simulate_world_boss_attack(player, boss, CFG, random.Random(seed)).damage / boss_hp
            for seed in range(20)
        ]
        average = sum(ratios) / len(ratios)
        assert 0.08 <= average <= 0.12
