import pytest
from pathlib import Path
import shutil
from game_core.config import load_config, validate_config, ConfigError
from game_core.models import GameConfig

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def test_load_real_config():
    cfg = load_config(DATA_DIR)
    assert isinstance(cfg, GameConfig)
    assert cfg.balance.stamina_max == 100
    assert "slime" in cfg.monsters
    assert cfg.monsters["slime"].depth_min == 1
    assert cfg.monsters["slime"].depth_max == 5
    assert cfg.monsters["slime"].defense == 1     # YAML 的 def 映射到 defense
    assert "hp_potion" in cfg.items
    assert cfg.items["hp_potion"].heal == 40
    assert any(e.type == "combat" for e in cfg.events)
    assert "world_boss_abyss_emperor" in cfg.world_bosses
    assert cfg.world_bosses["world_boss_abyss_emperor"].name == "万劫魔君"
    assert cfg.world_bosses["world_boss_abyss_emperor"].enabled is True


def test_load_world_boss_config_supports_disabled_bosses(tmp_path):
    data_dir = tmp_path / "data"
    shutil.copytree(DATA_DIR, data_dir)
    (data_dir / "world_bosses.yaml").write_text(
        """
- key: easy_boss
  name: 试炼魔君
  enabled: true
  tier: 1
  title: 入门
  atk: 100
  def: 30
  base_hp: 5000
  hp_per_active_player: 1000
  cooldown_hours: 6
  active_hours: 48
  reward_multiplier: 1.0
- key: hidden_boss
  name: 隐藏魔君
  enabled: false
  tier: 2
  title: 隐藏
  atk: 200
  def: 60
  base_hp: 10000
  hp_per_active_player: 2000
  cooldown_hours: 8
  active_hours: 48
  reward_multiplier: 1.3
""".strip(),
        encoding="utf-8",
    )

    cfg = load_config(data_dir)

    assert list(cfg.world_bosses) == ["easy_boss", "hidden_boss"]
    assert cfg.world_bosses["easy_boss"].title == "入门"
    assert cfg.world_bosses["hidden_boss"].enabled is False
    assert cfg.world_bosses["hidden_boss"].reward_multiplier == 1.3


def test_validate_rejects_world_boss_without_enabled_entries(tmp_path):
    data_dir = tmp_path / "data"
    shutil.copytree(DATA_DIR, data_dir)
    (data_dir / "world_bosses.yaml").write_text(
        """
- key: hidden_boss
  name: 隐藏魔君
  enabled: false
  tier: 1
  title: 隐藏
  atk: 100
  def: 30
  base_hp: 5000
  hp_per_active_player: 1000
  cooldown_hours: 6
  active_hours: 48
  reward_multiplier: 1.0
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="world_bosses"):
        load_config(data_dir)


def test_real_config_extends_to_depth_100():
    cfg = load_config(DATA_DIR)
    assert max(m.depth_max for m in cfg.monsters.values()) >= 100
    assert any(e.type == "treasure" and e.depth_max >= 100 for e in cfg.events)
    assert any(e.type == "trap" and e.depth_max >= 100 for e in cfg.events)


def test_real_config_has_expanded_gear_pool():
    cfg = load_config(DATA_DIR)
    gear = [it for it in cfg.items.values() if it.slot in {"weapon", "armor"}]
    assert len(gear) >= 70
    assert any(it.atk >= 100 for it in gear if it.slot == "weapon")
    assert any(it.defense >= 70 for it in gear if it.slot == "armor")


def test_validate_rejects_unknown_drop_item(tmp_path):
    cfg = load_config(DATA_DIR)
    cfg.monsters["slime"].drops.append(
        type(cfg.monsters["slime"].drops[0])(item="ghost_item", chance=0.1)
    )
    with pytest.raises(ConfigError, match="ghost_item"):
        validate_config(cfg)


def test_validate_rejects_nonpositive_weight():
    cfg = load_config(DATA_DIR)
    cfg.events[0].weight = 0
    with pytest.raises(ConfigError, match="weight"):
        validate_config(cfg)


def test_validate_rejects_reversed_monster_gold():
    cfg = load_config(DATA_DIR)
    m = cfg.monsters["slime"]
    m.gold_min, m.gold_max = 10, 1
    with pytest.raises(ConfigError, match="金币范围"):
        validate_config(cfg)


def test_validate_rejects_nonpositive_cost_per_step():
    cfg = load_config(DATA_DIR)
    cfg.balance.stamina_cost_per_step = 0
    with pytest.raises(ConfigError, match="cost_per_step"):
        validate_config(cfg)


def test_validate_rejects_nonpositive_regen_amount():
    cfg = load_config(DATA_DIR)
    cfg.balance.stamina_regen_amount = 0
    with pytest.raises(ConfigError, match="regen_amount"):
        validate_config(cfg)


def test_validate_rejects_zero_regen_minutes():
    cfg = load_config(DATA_DIR)
    cfg.balance.stamina_regen_minutes = 0
    with pytest.raises(ConfigError, match="regen_minutes"):
        validate_config(cfg)


def test_validate_rejects_empty_monsters():
    cfg = load_config(DATA_DIR)
    cfg.monsters.clear()
    with pytest.raises(ConfigError, match="怪物"):
        validate_config(cfg)


def test_validate_rejects_reversed_treasure_gold():
    cfg = load_config(DATA_DIR)
    treasure = next(e for e in cfg.events if e.type == "treasure")
    treasure.reward_gold = (30, 10)
    with pytest.raises(ConfigError, match="reward_gold"):
        validate_config(cfg)
