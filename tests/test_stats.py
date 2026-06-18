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
        InventoryItem(item_id="iron_sword", equipped=True),   # atk +5
        InventoryItem(item_id="leather_armor", equipped=True), # def +3, hp +35
        InventoryItem(item_id="hp_potion", equipped=False),    # 未装备,不计
    ])
    assert attack(p, CFG) == 10 + 5
    assert defense(p, CFG) == 5 + 3
    assert hp_max(p, CFG) == 100 + 35


def test_power_formula():
    p = _player(level=1)
    # power = atk*2 + def*2 + hp_max*0.5 = 10*2 + 5*2 + 100*0.5 = 80
    assert power(p, CFG) == 80
