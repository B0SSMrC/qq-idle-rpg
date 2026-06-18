from game_core.models import Player
from game_core.ranking import rank_players


def _p(name, level, max_depth):
    return Player(group_id="g", user_id=name, name=name,
                  level=level, max_depth=max_depth)


def test_rank_by_level_then_depth():
    players = [_p("A", 3, 5), _p("B", 5, 2), _p("C", 5, 9)]
    ranked = rank_players(players, key="level", limit=10)
    assert [p.name for p in ranked] == ["C", "B", "A"]   # 5级C(深9)>5级B(深2)>3级A


def test_rank_by_depth():
    players = [_p("A", 3, 5), _p("B", 5, 2), _p("C", 5, 9)]
    ranked = rank_players(players, key="depth", limit=10)
    assert [p.name for p in ranked] == ["C", "A", "B"]   # 深 9 > 5 > 2


def test_limit_applies():
    players = [_p(str(i), i, i) for i in range(1, 21)]
    ranked = rank_players(players, key="level", limit=10)
    assert len(ranked) == 10
    assert ranked[0].name == "20"
