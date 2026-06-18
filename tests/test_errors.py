from game_core.errors import (
    GameError, NotEnoughStamina, CharacterNotFound,
    DuplicateName, ItemNotFound, NotEnoughGold, InvalidSlot,
)


def test_domain_errors_are_gameerror_subclasses():
    for cls in (NotEnoughStamina, CharacterNotFound, DuplicateName,
                ItemNotFound, NotEnoughGold, InvalidSlot):
        assert issubclass(cls, GameError)


def test_error_carries_message():
    err = NotEnoughStamina("体力不够")
    assert str(err) == "体力不够"
    assert isinstance(err, GameError)
