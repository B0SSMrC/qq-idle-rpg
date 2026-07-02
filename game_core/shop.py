from __future__ import annotations
import random
from game_core.models import Player, GameConfig, ItemDef
from game_core.loot import add_item
from game_core.errors import NotEnoughGold, ItemNotFound


def list_shop(cfg: GameConfig) -> list[ItemDef]:
    """所有标了 price 的物品即在售。"""
    return [it for it in cfg.items.values() if it.price is not None]


def buy(player: Player, item_id: str, cfg: GameConfig,
        rng: random.Random | None = None):
    item = cfg.items.get(item_id)
    if item is None or item.price is None:
        raise ItemNotFound(f"商店没有这件商品: {item_id}")
    if player.gold < item.price:
        raise NotEnoughGold(f"金币不足(需 {item.price},当前 {player.gold})")
    player.gold -= item.price
    return add_item(player, item_id, cfg=cfg, rng=rng)
