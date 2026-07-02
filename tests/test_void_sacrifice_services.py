from __future__ import annotations

import random
from pathlib import Path

import pytest

from app import services
from game_core.config import load_config
from game_core.errors import GameError, NotEnoughGold
from game_core.models import Player
from game_core.void_sacrifice import VoidSacrificePity
from storage import db, repository as repo, void_sacrifice_repo


CFG = load_config(Path("data"))


def _conn():
    conn = db.get_conn(":memory:")
    db.init_db(conn)
    return conn


def _player(conn, *, gold=20000, group_id="g", user_id="u"):
    player = Player(
        group_id=group_id,
        user_id=user_id,
        name=f"p-{group_id}-{user_id}",
        gold=gold,
        stamina=100,
        stamina_at=1000,
        current_hp=100,
        created_at=1000,
        last_active_at=1000,
    )
    return repo.create_player(conn, player)


def test_do_void_sacrifice_single_draw_deducts_gold_and_persists_pity():
    conn = _conn()
    _player(conn, gold=20000)

    result = services.do_void_sacrifice(
        conn, CFG, "g", "u", 1, now=2000, rng=random.Random(5)
    )

    saved = repo.get_player(conn, "g", "u")
    pity = void_sacrifice_repo.get_pity(conn, "g", "u")
    assert result.cost == 1000
    assert result.draw_count == 1
    assert len(result.draws) == 1
    assert saved.gold == result.player.gold
    assert saved.gold <= 19000 + 320
    assert pity.total_draws == 1


def test_do_void_sacrifice_ten_draw_deducts_gold_and_grants_ten_entries():
    conn = _conn()
    _player(conn, gold=20000)

    result = services.do_void_sacrifice(
        conn, CFG, "g", "u", 10, now=2000, rng=random.Random(3)
    )

    assert result.cost == 10000
    assert result.draw_count == 10
    assert len(result.draws) == 10
    assert result.pity.total_draws == 10
    assert any(d.rarity in {"epic", "legendary", "mythic", "divine"} for d in result.draws)


def test_do_void_sacrifice_insufficient_gold_deducts_nothing_and_keeps_pity():
    conn = _conn()
    _player(conn, gold=999)

    with pytest.raises(NotEnoughGold, match="金币不足"):
        services.do_void_sacrifice(conn, CFG, "g", "u", 1, now=2000, rng=random.Random(1))

    saved = repo.get_player(conn, "g", "u")
    pity = void_sacrifice_repo.get_pity(conn, "g", "u")
    assert saved.gold == 999
    assert pity == VoidSacrificePity()


def test_do_void_sacrifice_rejects_invalid_count():
    conn = _conn()
    _player(conn, gold=20000)

    with pytest.raises(GameError, match="用法:虚空献祭"):
        services.do_void_sacrifice(conn, CFG, "g", "u", 2, now=2000, rng=random.Random(1))


def test_do_void_sacrifice_pity_is_scoped_by_group_and_user():
    conn = _conn()
    _player(conn, gold=20000, group_id="g1", user_id="u")
    _player(conn, gold=20000, group_id="g2", user_id="u")

    services.do_void_sacrifice(conn, CFG, "g1", "u", 1, now=2000, rng=random.Random(1))

    assert void_sacrifice_repo.get_pity(conn, "g1", "u").total_draws == 1
    assert void_sacrifice_repo.get_pity(conn, "g2", "u").total_draws == 0
