import pytest
from pathlib import Path
from game_core.config import load_config, validate_config, ConfigError
from game_core.models import GameConfig

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def test_load_real_config():
    cfg = load_config(DATA_DIR)
    assert isinstance(cfg, GameConfig)
    assert cfg.balance.stamina_max == 50
    assert "slime" in cfg.monsters
    assert cfg.monsters["slime"].depth_min == 1
    assert cfg.monsters["slime"].depth_max == 5
    assert cfg.monsters["slime"].defense == 1     # YAML 的 def 映射到 defense
    assert "hp_potion" in cfg.items
    assert cfg.items["hp_potion"].heal == 50
    assert any(e.type == "combat" for e in cfg.events)


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
