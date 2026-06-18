import pytest
from pathlib import Path
from game_core.config import load_config
from game_core.models import Player
from game_core.shop import list_shop, buy
from game_core.errors import NotEnoughGold, ItemNotFound

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CFG = load_config(DATA_DIR)


def test_list_shop_only_priced_items():
    items = list_shop(CFG)
    ids = {i.id for i in items}
    assert "hp_potion" in ids          # 有 price
    assert all(i.price is not None for i in items)


def test_buy_deducts_gold_and_adds_item():
    p = Player(group_id="g", user_id="u", name="勇者", gold=100)
    buy(p, "hp_potion", CFG)           # price 15
    assert p.gold == 85
    assert any(i.item_id == "hp_potion" for i in p.inventory)


def test_buy_insufficient_gold():
    p = Player(group_id="g", user_id="u", name="勇者", gold=10)
    with pytest.raises(NotEnoughGold):
        buy(p, "hp_potion", CFG)       # 需 20
    assert p.gold == 10                # 失败不扣钱


def test_buy_unknown_item():
    p = Player(group_id="g", user_id="u", name="勇者", gold=999)
    with pytest.raises(ItemNotFound):
        buy(p, "dragon_egg", CFG)
