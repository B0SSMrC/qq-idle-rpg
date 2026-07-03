import json
import random
from pathlib import Path

import pytest

from app import services
from game_core.config import load_config
from game_core.models import InventoryItem, Player
from storage import db, repository as repo, world_boss_repo


CFG = load_config(Path("data"))


def _conn():
    conn = db.get_conn(":memory:")
    db.init_db(conn)
    return conn


def _player(conn, user_id="u", name="cxh", stamina=100, gold=1000, hp=300):
    p = Player(
        group_id="g",
        user_id=user_id,
        name=name,
        level=30,
        gold=gold,
        stamina=stamina,
        stamina_at=1000,
        current_hp=hp,
        created_at=1000,
        last_active_at=1000,
    )
    p.inventory = [
        InventoryItem(item_id="iron_sword", equipped=True),
        InventoryItem(item_id="cloth_armor", equipped=True),
    ]
    return repo.create_player(conn, p)


def test_world_boss_status_spawns_group_boss():
    conn = _conn()
    _player(conn)

    result = services.do_world_boss_status(conn, CFG, "g", now=1000)

    assert result.boss is not None
    assert result.boss["group_id"] == "g"
    assert result.boss["hp_current"] == result.boss["hp_max"]
    assert result.damage_entries == []


def test_world_boss_status_spawns_all_enabled_configured_bosses():
    conn = _conn()
    _player(conn)

    result = services.do_world_boss_status(conn, CFG, "g", now=1000)

    assert [boss["boss_key"] for boss in result.bosses] == [
        "world_boss_abyss_emperor",
        "burning_warlord",
        "ocean_dragon",
        "void_star_lord",
    ]
    assert result.boss["boss_key"] == "world_boss_abyss_emperor"


def test_attack_world_boss_consumes_stamina_records_damage_and_defeat_penalty():
    conn = _conn()
    _player(conn, stamina=100, gold=1000, hp=300)
    services.do_world_boss_status(conn, CFG, "g", now=1000)

    result = services.do_attack_world_boss(conn, CFG, "g", "u", now=1001, rng=random.Random(1))

    updated = repo.get_player(conn, "g", "u")
    boss = world_boss_repo.get_active_boss(conn, "g")
    damage_rows = world_boss_repo.list_damage(conn, result.boss_id)

    assert result.damage > 0
    assert result.player_defeated is True
    assert updated.stamina == 50
    assert updated.gold == 950
    assert updated.current_hp > 300
    assert boss["hp_current"] == boss["hp_max"] - result.damage
    assert damage_rows[0]["damage"] == result.damage
    assert damage_rows[0]["attack_count"] == 1


def test_attack_world_boss_can_select_configured_boss_by_tier():
    conn = _conn()
    _player(conn, stamina=100, gold=1000, hp=300)
    services.do_world_boss_status(conn, CFG, "g", now=1000)

    result = services.do_attack_world_boss(
        conn, CFG, "g", "u", now=1001, rng=random.Random(1), boss_query="2"
    )
    active = world_boss_repo.get_active_boss(conn, "g", "burning_warlord")

    assert result.boss_name == "焚天战魁"
    assert result.boss_id == active["id"]
    assert active["hp_current"] == active["hp_max"] - result.damage


def test_attack_world_boss_rejects_low_stamina():
    conn = _conn()
    _player(conn, stamina=49)
    services.do_world_boss_status(conn, CFG, "g", now=1000)

    with pytest.raises(Exception, match="体力不足"):
        services.do_attack_world_boss(conn, CFG, "g", "u", now=1001, rng=random.Random(1))


def test_attack_world_boss_defeat_creates_rewards_once():
    conn = _conn()
    p = _player(conn, stamina=100, gold=1000, hp=5000)
    p.level = 100
    p.inventory = [
        InventoryItem(item_id="silent_ending_needles", equipped=True),
        InventoryItem(item_id="heaven_fortress_plate", equipped=True),
    ]
    repo.save_player(conn, p)
    boss = services.do_world_boss_status(conn, CFG, "g", now=1000).boss
    conn.execute(
        "UPDATE world_bosses SET hp_current=10, atk=1, def=1 WHERE id=?",
        (boss["id"],),
    )
    conn.commit()

    result = services.do_attack_world_boss(conn, CFG, "g", "u", now=1001, rng=random.Random(2))
    rows = conn.execute("SELECT * FROM world_boss_rewards WHERE boss_id=?", (boss["id"],)).fetchall()
    defeated = conn.execute("SELECT * FROM world_bosses WHERE id=?", (boss["id"],)).fetchone()

    assert result.boss_defeated is True
    assert defeated["status"] == "dead"
    assert len(rows) == 1


def test_high_tier_world_boss_rewards_growth_gold_and_materials():
    conn = _conn()
    p = _player(conn, stamina=100, gold=500, hp=5000)
    p.level = 60
    p.max_depth = 95
    p.inventory = [
        InventoryItem(item_id="phoenix_feather_armor", equipped=True),
        InventoryItem(item_id="soul_lock_nails", equipped=True),
    ]
    repo.save_player(conn, p)
    boss = services.do_world_boss_status(conn, CFG, "g", now=1000, boss_query="4").boss
    conn.execute(
        "UPDATE world_bosses SET hp_max=500, hp_current=10, atk=1, def=1 WHERE id=?",
        (boss["id"],),
    )
    conn.commit()

    result = services.do_attack_world_boss(
        conn, CFG, "g", "u", now=1001, rng=random.Random(4), boss_query="4"
    )
    row = conn.execute("SELECT * FROM world_boss_rewards WHERE boss_id=?", (boss["id"],)).fetchone()
    items = json.loads(row["items_json"])
    material_ids = {item_id for item_id, _ in items}

    assert result.boss_defeated is True
    assert row["gold"] > CFG.world_bosses["void_star_lord"].min_gold
    assert material_ids & {"star_meteorite", "divine_forge_crystal"}


def test_attack_world_boss_retries_version_conflict(monkeypatch):
    conn = _conn()
    _player(conn, stamina=100, gold=1000, hp=300)
    services.do_world_boss_status(conn, CFG, "g", now=1000)
    calls = {"count": 0}
    original = world_boss_repo.apply_boss_damage

    def flaky_apply(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return False
        return original(*args, **kwargs)

    monkeypatch.setattr(world_boss_repo, "apply_boss_damage", flaky_apply)

    result = services.do_attack_world_boss(conn, CFG, "g", "u", now=1001, rng=random.Random(1))

    assert result.damage > 0
    assert calls["count"] == 2


def test_world_boss_announcements_are_due_every_ten_minutes():
    conn = _conn()
    _player(conn)
    boss = services.do_world_boss_status(conn, CFG, "g", now=1000).boss

    assert services.get_due_world_boss_announcements(conn, CFG, now=1599) == []
    due = services.get_due_world_boss_announcements(conn, CFG, now=1600)
    assert len(due) == 1
    assert due[0].boss["id"] == boss["id"]
    assert len(due[0].bosses) == 4

    for due_boss in due[0].bosses:
        services.mark_world_boss_announced(conn, due_boss["id"], now=1600)
    assert services.get_due_world_boss_announcements(conn, CFG, now=2199) == []


def test_world_boss_announcements_skip_recent_updates():
    conn = _conn()
    _player(conn)
    boss = services.do_world_boss_status(conn, CFG, "g", now=1000).boss
    for due_boss in world_boss_repo.list_active_bosses(conn, "g"):
        conn.execute(
            "UPDATE world_bosses SET last_announcement_at=900, updated_at=1598 WHERE id=?",
            (due_boss["id"],),
        )
    conn.commit()

    assert services.get_due_world_boss_announcements(conn, CFG, now=1600) == []
