from pathlib import Path
from game_core.config import load_config
from game_core.models import Player, InventoryItem
from game_core.models import Buff
from game_core.stats import hp_max, attack, defense, lifesteal, power

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CFG = load_config(DATA_DIR)


def _player(level=1, inv=None):
    p = Player(group_id="g", user_id="u", name="勇者", level=level)
    p.inventory = inv or []
    return p


def test_base_stats_level_1():
    p = _player(level=1)
    assert hp_max(p, CFG) == 120      # base_hp
    assert attack(p, CFG) == 12       # base_atk
    assert defense(p, CFG) == 7       # base_def


def test_stats_grow_with_level():
    p = _player(level=3)              # +2 级
    assert hp_max(p, CFG) == 120 + 24 * 2
    assert attack(p, CFG) == 12 + 4 * 2
    assert defense(p, CFG) == 7 + 2 * 2


def test_equipped_items_add_stats():
    p = _player(level=1, inv=[
        InventoryItem(item_id="iron_sword", equipped=True),   # atk +5
        InventoryItem(item_id="leather_armor", equipped=True), # def +3, hp +35
        InventoryItem(item_id="hp_potion", equipped=False),    # 未装备,不计
    ])
    assert attack(p, CFG) == 12 + 5
    assert defense(p, CFG) == 7 + 3
    assert hp_max(p, CFG) == 120 + 35


def test_power_formula():
    p = _player(level=1)
    # power = atk*2 + def*2 + hp_max*0.5 = 12*2 + 7*2 + 120*0.5 = 98
    assert power(p, CFG) == 98


def test_attack_includes_atk_buff():
    p = _player(level=1)
    p.buffs.append(Buff(type="atk", amount=10, steps_left=3))
    assert attack(p, CFG) == 12 + 10  # base + buff


def test_defense_includes_def_buff():
    p = _player(level=1)
    p.buffs.append(Buff(type="def", amount=5, steps_left=2))
    assert defense(p, CFG) == 7 + 5  # base + buff


def test_buffs_no_effect_on_wrong_type():
    p = _player(level=1)
    p.buffs.append(Buff(type="def", amount=10, steps_left=1))
    # def buff should NOT affect attack
    assert attack(p, CFG) == 12


def test_overdrive_reduces_attack_and_defense_until_expiry():
    p = _player(level=1)
    p.last_active_at = 1000
    p.overdrive_until = 1300
    assert attack(p, CFG) == int(12 * 0.85)
    assert defense(p, CFG) == int(7 * 0.8)

    p.last_active_at = 1300
    assert attack(p, CFG) == 12
    assert defense(p, CFG) == 7


def test_equipped_affixes_modify_stats():
    p = _player(level=1, inv=[
        InventoryItem(
            item_id="iron_sword",
            equipped=True,
            affix='{"name":"锋锐","effects":{"atk_pct":0.2}}',
        ),
        InventoryItem(
            item_id="leather_armor",
            equipped=True,
            affix='{"name":"厚血","effects":{"hp_pct":0.1}}',
        ),
    ])
    assert attack(p, CFG) == int((12 + 5) * 1.2)
    assert hp_max(p, CFG) == int((120 + 35) * 1.1)


def test_equipment_growth_increases_player_stats_before_affixes():
    p = _player(level=1)
    p.inventory = [
        InventoryItem(
            item_id="iron_sword",
            equipped=True,
            enhance_level=5,
            star_level=1,
            affix='{"name":"閿嬮攼","effects":{"atk_pct":0.2}}',
        ),
        InventoryItem(item_id="cloth_armor", equipped=True, enhance_level=5),
    ]

    assert attack(p, CFG) == 21
    assert defense(p, CFG) == 10
    assert hp_max(p, CFG) == 144


def test_lifesteal_reads_weapon_affix():
    p = _player(level=1, inv=[
        InventoryItem(
            item_id="iron_sword",
            equipped=True,
            affix='{"name":"嗜血","effects":{"lifesteal_pct":0.12}}',
        ),
    ])
    assert lifesteal(p, CFG) == 0.12
