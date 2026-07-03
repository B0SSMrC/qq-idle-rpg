from pathlib import Path

from game_core.config import load_config
from storage import db
from storage import world_boss_repo

CFG = load_config(Path("data"))


def test_init_db_creates_world_boss_tables():
    conn = db.get_conn(":memory:")
    db.init_db(conn)

    tables = {
        r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }

    assert {"world_bosses", "world_boss_damage", "world_boss_rewards"} <= tables


def test_create_or_get_active_boss_is_group_scoped_and_idempotent():
    conn = db.get_conn(":memory:")
    db.init_db(conn)

    first = world_boss_repo.create_or_get_active_boss(
        conn, "g1", now=1000, active_player_count=3
    )
    second = world_boss_repo.create_or_get_active_boss(
        conn, "g1", now=1010, active_player_count=10
    )
    other_group = world_boss_repo.create_or_get_active_boss(
        conn, "g2", now=1010, active_player_count=1
    )

    assert first["id"] == second["id"]
    assert first["group_id"] == "g1"
    assert first["hp_max"] == 18000
    assert other_group["id"] != first["id"]


def test_create_or_get_active_boss_is_boss_key_scoped():
    conn = db.get_conn(":memory:")
    db.init_db(conn)
    easy = CFG.world_bosses["world_boss_abyss_emperor"]
    hard = CFG.world_bosses["burning_warlord"]

    first_easy = world_boss_repo.create_or_get_active_boss(
        conn, "g1", now=1000, active_player_count=2, boss_def=easy
    )
    second_easy = world_boss_repo.create_or_get_active_boss(
        conn, "g1", now=1010, active_player_count=5, boss_def=easy
    )
    hard_boss = world_boss_repo.create_or_get_active_boss(
        conn, "g1", now=1010, active_player_count=2, boss_def=hard
    )

    assert first_easy["id"] == second_easy["id"]
    assert hard_boss["id"] != first_easy["id"]
    assert hard_boss["boss_key"] == "burning_warlord"
    assert hard_boss["hp_max"] == hard.base_hp + 2 * hard.hp_per_active_player
    assert [row["boss_key"] for row in world_boss_repo.list_active_bosses(conn, "g1")] == [
        "world_boss_abyss_emperor",
        "burning_warlord",
    ]


def test_boss_cooldown_is_scoped_to_boss_key():
    conn = db.get_conn(":memory:")
    db.init_db(conn)
    easy = CFG.world_bosses["world_boss_abyss_emperor"]
    hard = CFG.world_bosses["burning_warlord"]
    easy_boss = world_boss_repo.create_or_get_active_boss(
        conn, "g1", now=1000, active_player_count=1, boss_def=easy
    )
    conn.execute(
        "UPDATE world_bosses SET status='dead', hp_current=0, next_spawn_at=? WHERE id=?",
        (1000 + easy.cooldown_seconds, easy_boss["id"]),
    )
    conn.commit()

    assert world_boss_repo.create_or_get_active_boss(
        conn, "g1", now=2000, active_player_count=1, boss_def=easy
    ) is None
    hard_boss = world_boss_repo.create_or_get_active_boss(
        conn, "g1", now=2000, active_player_count=1, boss_def=hard
    )

    assert hard_boss is not None
    assert hard_boss["boss_key"] == "burning_warlord"


def test_create_or_get_active_boss_retunes_legacy_alive_boss():
    conn = db.get_conn(":memory:")
    db.init_db(conn)
    boss = world_boss_repo.create_or_get_active_boss(
        conn, "g1", now=1000, active_player_count=2
    )
    conn.execute(
        """
        UPDATE world_bosses
        SET hp_max=210000,
            hp_current=105000,
            atk=360,
            def=180,
            version=2
        WHERE id=?
        """,
        (boss["id"],),
    )
    world_boss_repo.add_damage(
        conn, boss["id"], "g1", "u1", "cxh", damage=63000, now=1005
    )
    world_boss_repo.add_damage(
        conn, boss["id"], "g1", "u2", "Crazy", damage=42000, now=1006
    )
    conn.commit()

    retuned = world_boss_repo.create_or_get_active_boss(
        conn, "g1", now=1010, active_player_count=2
    )

    assert retuned["id"] == boss["id"]
    assert retuned["hp_max"] == 15000
    assert retuned["hp_current"] == 7500
    assert retuned["atk"] == world_boss_repo.WORLD_BOSS_ATK
    assert retuned["def"] == world_boss_repo.WORLD_BOSS_DEF
    assert retuned["version"] == 3
    damage_rows = world_boss_repo.list_damage(conn, boss["id"])
    assert [row["damage"] for row in damage_rows] == [4500, 3000]


def test_due_announcements_only_returns_alive_bosses_after_interval():
    conn = db.get_conn(":memory:")
    db.init_db(conn)
    boss = world_boss_repo.create_or_get_active_boss(
        conn, "g1", now=1000, active_player_count=1
    )

    assert world_boss_repo.list_due_announcements(conn, now=1599) == []
    due = world_boss_repo.list_due_announcements(conn, now=1600)
    assert [row["id"] for row in due] == [boss["id"]]

    world_boss_repo.mark_announced(conn, boss["id"], now=1600)
    assert world_boss_repo.list_due_announcements(conn, now=2199) == []


def test_create_or_get_active_boss_respects_defeat_cooldown():
    conn = db.get_conn(":memory:")
    db.init_db(conn)
    boss = world_boss_repo.create_or_get_active_boss(
        conn, "g1", now=1000, active_player_count=1
    )
    conn.execute(
        "UPDATE world_bosses SET status='dead', hp_current=0, next_spawn_at=? WHERE id=?",
        (1000 + world_boss_repo.WORLD_BOSS_COOLDOWN_SECONDS, boss["id"]),
    )
    conn.commit()

    assert world_boss_repo.create_or_get_active_boss(
        conn, "g1", now=2000, active_player_count=1
    ) is None
    respawned = world_boss_repo.create_or_get_active_boss(
        conn,
        "g1",
        now=1000 + world_boss_repo.WORLD_BOSS_COOLDOWN_SECONDS,
        active_player_count=1,
    )
    assert respawned is not None
    assert respawned["id"] != boss["id"]


def test_create_or_get_active_boss_expires_old_alive_boss_into_cooldown():
    conn = db.get_conn(":memory:")
    db.init_db(conn)
    boss = world_boss_repo.create_or_get_active_boss(
        conn, "g1", now=1000, active_player_count=1
    )
    conn.execute("UPDATE world_bosses SET expires_at=? WHERE id=?", (1200, boss["id"]))
    conn.commit()

    assert world_boss_repo.create_or_get_active_boss(
        conn, "g1", now=1201, active_player_count=1
    ) is None
    expired = conn.execute("SELECT * FROM world_bosses WHERE id=?", (boss["id"],)).fetchone()
    assert expired["status"] == "escaped"
