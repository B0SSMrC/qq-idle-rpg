from __future__ import annotations

import random
from pathlib import Path

import pytest

from app import services
from game_core.config import load_config
from game_core.errors import GameError, NotEnoughGold
from game_core.models import Player
from game_core.void_sacrifice import (
    VOID_SACRIFICE_SINGLE_COST,
    VoidSacrificeDraw,
    VoidSacrificePity,
    VoidSacrificeRoll,
)
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


def test_do_void_sacrifice_persists_common_consumable_reward(monkeypatch):
    conn = _conn()
    _player(conn, gold=20000)

    monkeypatch.setattr(
        services,
        "roll_void_sacrifice",
        lambda draw_count, cfg, rng, pity: VoidSacrificeRoll(
            draws=[VoidSacrificeDraw(rarity="common", consumable_id="hp_potion")],
            pity=VoidSacrificePity(total_draws=1, draws_since_mythic_plus=1, draws_since_divine=1),
        ),
    )

    result = services.do_void_sacrifice(conn, CFG, "g", "u", 1, now=2000, rng=random.Random(7))

    reloaded = repo.get_player(conn, "g", "u")
    potions = [item for item in reloaded.inventory if item.item_id == "hp_potion"]
    assert result.player.gold == 20000 - VOID_SACRIFICE_SINGLE_COST
    assert len(potions) == 1
    assert potions[0].quantity == 1


def test_do_void_sacrifice_persists_gear_reward_via_loot_path_with_affix(monkeypatch):
    conn = _conn()
    _player(conn, gold=20000)
    add_item_calls: list[tuple[str, int, str]] = []
    real_add_item = services._loot.add_item

    def tracking_add_item(player, item_id, qty=1, cfg=None, rng=None, source=""):
        add_item_calls.append((item_id, qty, source))
        return real_add_item(player, item_id, qty=qty, cfg=cfg, rng=rng, source=source)

    monkeypatch.setattr(
        services,
        "roll_void_sacrifice",
        lambda draw_count, cfg, rng, pity: VoidSacrificeRoll(
            draws=[VoidSacrificeDraw(rarity="rare", item_id="iron_sword")],
            pity=VoidSacrificePity(total_draws=1, draws_since_mythic_plus=1, draws_since_divine=1),
        ),
    )
    monkeypatch.setattr(services._loot, "add_item", tracking_add_item)

    services.do_void_sacrifice(conn, CFG, "g", "u", 1, now=2000, rng=random.Random(11))

    reloaded = repo.get_player(conn, "g", "u")
    swords = [item for item in reloaded.inventory if item.item_id == "iron_sword"]
    assert add_item_calls == [("iron_sword", 1, "void_sacrifice")]
    assert len(swords) == 1
    assert swords[0].quantity == 1
    assert swords[0].affix
    assert swords[0].source == "void_sacrifice"


def test_do_void_sacrifice_deducts_gold_before_rolling_rewards(monkeypatch):
    conn = _conn()
    _player(conn, gold=20000)
    real_require = services._require
    captured_player: list[Player] = []
    require_calls = {"count": 0}

    def tracking_require(conn_arg, cfg, group_id, user_id):
        require_calls["count"] += 1
        player = real_require(conn_arg, cfg, group_id, user_id)
        if require_calls["count"] == 2:
            captured_player.append(player)
        return player

    def controlled_roll(draw_count, cfg, rng, pity):
        assert captured_player, "expected in-transaction player to be captured before roll"
        assert captured_player[0].gold == 20000 - VOID_SACRIFICE_SINGLE_COST
        return VoidSacrificeRoll(
            draws=[VoidSacrificeDraw(rarity="common", gold_refund=0)],
            pity=VoidSacrificePity(total_draws=1, draws_since_mythic_plus=1, draws_since_divine=1),
        )

    monkeypatch.setattr(services, "_require", tracking_require)
    monkeypatch.setattr(services, "roll_void_sacrifice", controlled_roll)

    services.do_void_sacrifice(conn, CFG, "g", "u", 1, now=2000, rng=random.Random(13))
