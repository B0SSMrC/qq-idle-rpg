class GameError(Exception):
    """所有可向玩家友好展示的业务错误的基类。"""


class NotEnoughStamina(GameError):
    """体力不足以执行该操作。"""


class CharacterNotFound(GameError):
    """该玩家在本群尚无角色。"""


class DuplicateName(GameError):
    """同群内角色名重复。"""


class ItemNotFound(GameError):
    """物品在配置或背包中不存在。"""


class NotEnoughGold(GameError):
    """金币不足。"""


class InvalidSlot(GameError):
    """装备槽位不匹配(例如把消耗品当武器装备)。"""
