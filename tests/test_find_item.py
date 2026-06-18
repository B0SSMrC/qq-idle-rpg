import pytest
from pathlib import Path
from game_core.config import load_config, find_item_id
from game_core.errors import ItemNotFound

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CFG = load_config(DATA_DIR)


def test_find_by_id():
    assert find_item_id(CFG, "hp_potion") == "hp_potion"


def test_find_by_chinese_name():
    assert find_item_id(CFG, "金疮药") == "hp_potion"


def test_find_unknown_raises():
    with pytest.raises(ItemNotFound):
        find_item_id(CFG, "屠龙刀")
