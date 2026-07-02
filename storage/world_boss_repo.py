from __future__ import annotations

import sqlite3

WORLD_BOSS_KEY = "world_boss_abyss_emperor"
WORLD_BOSS_NAME = "万劫魔君"
WORLD_BOSS_ATK = 180
WORLD_BOSS_DEF = 70
WORLD_BOSS_BASE_HP = 9_000
WORLD_BOSS_HP_PER_ACTIVE_PLAYER = 3_000
WORLD_BOSS_COOLDOWN_SECONDS = 6 * 60 * 60
WORLD_BOSS_ACTIVE_SECONDS = 48 * 60 * 60
WORLD_BOSS_ANNOUNCE_SECONDS = 10 * 60
WORLD_BOSS_RECENT_UPDATE_GRACE_SECONDS = 3


def _row(conn: sqlite3.Connection, boss_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM world_bosses WHERE id=?", (boss_id,)).fetchone()
    if row is None:  # pragma: no cover - defensive guard
        raise RuntimeError(f"world boss {boss_id} disappeared")
    return row


def get_active_boss(conn: sqlite3.Connection, group_id: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT * FROM world_bosses
        WHERE group_id=? AND status='alive'
        ORDER BY id DESC
        LIMIT 1
        """,
        (group_id,),
    ).fetchone()


def _target_hp_max(active_player_count: int) -> int:
    return WORLD_BOSS_BASE_HP + max(1, active_player_count) * WORLD_BOSS_HP_PER_ACTIVE_PLAYER


def _scale_positive_int(value: int, old_total: int, new_total: int) -> int:
    if value <= 0:
        return 0
    return max(1, (value * new_total + old_total // 2) // old_total)


def _retune_alive_boss_if_needed(
    conn: sqlite3.Connection,
    boss: sqlite3.Row,
    now: int,
    active_player_count: int,
) -> sqlite3.Row:
    target_hp_max = _target_hp_max(active_player_count)
    old_hp_max = max(1, int(boss["hp_max"]))
    oversized_legacy_hp = old_hp_max > target_hp_max * 3
    stale_stats = int(boss["atk"]) != WORLD_BOSS_ATK or int(boss["def"]) != WORLD_BOSS_DEF
    if not oversized_legacy_hp and not stale_stats:
        return boss

    hp_current = min(
        target_hp_max,
        _scale_positive_int(int(boss["hp_current"]), old_hp_max, target_hp_max),
    )
    conn.execute(
        """
        UPDATE world_bosses
        SET hp_max=?,
            hp_current=?,
            atk=?,
            def=?,
            version=version + 1,
            updated_at=?
        WHERE id=? AND status='alive'
        """,
        (
            target_hp_max,
            hp_current,
            WORLD_BOSS_ATK,
            WORLD_BOSS_DEF,
            now,
            boss["id"],
        ),
    )
    for row in list_damage(conn, boss["id"]):
        scaled_damage = _scale_positive_int(int(row["damage"]), old_hp_max, target_hp_max)
        conn.execute(
            """
            UPDATE world_boss_damage
            SET damage=?,
                updated_at=?
            WHERE boss_id=? AND user_id=?
            """,
            (scaled_damage, now, boss["id"], row["user_id"]),
        )
    conn.commit()
    return _row(conn, boss["id"])


def create_or_get_active_boss(
    conn: sqlite3.Connection,
    group_id: str,
    now: int,
    active_player_count: int,
) -> sqlite3.Row | None:
    existing = get_active_boss(conn, group_id)
    if existing is not None:
        if existing["expires_at"] <= now:
            conn.execute(
                """
                UPDATE world_bosses
                SET status='escaped',
                    next_spawn_at=?,
                    updated_at=?
                WHERE id=? AND status='alive'
                """,
                (now + WORLD_BOSS_COOLDOWN_SECONDS, now, existing["id"]),
            )
            conn.commit()
            return None
        return _retune_alive_boss_if_needed(conn, existing, now, active_player_count)

    cooldown = conn.execute(
        """
        SELECT * FROM world_bosses
        WHERE group_id=? AND status IN ('dead', 'escaped') AND next_spawn_at>?
        ORDER BY next_spawn_at DESC
        LIMIT 1
        """,
        (group_id, now),
    ).fetchone()
    if cooldown is not None:
        return None

    hp_max = _target_hp_max(active_player_count)
    cur = conn.execute(
        """
        INSERT INTO world_bosses (
            group_id,boss_key,name,hp_max,hp_current,atk,def,status,version,
            spawned_at,expires_at,next_spawn_at,last_announcement_at,updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            group_id,
            WORLD_BOSS_KEY,
            WORLD_BOSS_NAME,
            hp_max,
            hp_max,
            WORLD_BOSS_ATK,
            WORLD_BOSS_DEF,
            "alive",
            0,
            now,
            now + WORLD_BOSS_ACTIVE_SECONDS,
            0,
            now,
            now,
        ),
    )
    conn.commit()
    return _row(conn, cur.lastrowid)


def list_due_announcements(conn: sqlite3.Connection, now: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT * FROM world_bosses
        WHERE status='alive'
          AND ? - last_announcement_at >= ?
          AND ? - updated_at >= ?
        ORDER BY group_id
        """,
        (
            now,
            WORLD_BOSS_ANNOUNCE_SECONDS,
            now,
            WORLD_BOSS_RECENT_UPDATE_GRACE_SECONDS,
        ),
    ).fetchall()


def mark_announced(conn: sqlite3.Connection, boss_id: int, now: int) -> None:
    conn.execute(
        "UPDATE world_bosses SET last_announcement_at=? WHERE id=?",
        (now, boss_id),
    )
    conn.commit()


def count_active_players(conn: sqlite3.Connection, group_id: str, now: int) -> int:
    active_since = now - 7 * 24 * 60 * 60
    row = conn.execute(
        "SELECT COUNT(*) AS count FROM players WHERE group_id=? AND last_active_at>=?",
        (group_id, active_since),
    ).fetchone()
    return int(row["count"] if row else 0)


def get_boss(conn: sqlite3.Connection, boss_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM world_bosses WHERE id=?", (boss_id,)).fetchone()


def apply_boss_damage(
    conn: sqlite3.Connection,
    boss_id: int,
    old_version: int,
    effective_damage: int,
    now: int,
) -> bool:
    cur = conn.execute(
        """
        UPDATE world_bosses
        SET hp_current = MAX(0, hp_current - ?),
            status = CASE
              WHEN hp_current - ? <= 0 THEN 'dead'
              ELSE 'alive'
            END,
            next_spawn_at = CASE
              WHEN hp_current - ? <= 0 THEN ?
              ELSE next_spawn_at
            END,
            version = version + 1,
            updated_at = ?
        WHERE id=?
          AND status='alive'
          AND version=?
        """,
        (
            effective_damage,
            effective_damage,
            effective_damage,
            now + WORLD_BOSS_COOLDOWN_SECONDS,
            now,
            boss_id,
            old_version,
        ),
    )
    return cur.rowcount == 1


def add_damage(
    conn: sqlite3.Connection,
    boss_id: int,
    group_id: str,
    user_id: str,
    player_name: str,
    damage: int,
    now: int,
) -> None:
    conn.execute(
        """
        INSERT INTO world_boss_damage (
            boss_id,group_id,user_id,player_name,damage,attack_count,updated_at
        ) VALUES (?,?,?,?,?,?,?)
        ON CONFLICT(boss_id, user_id) DO UPDATE SET
            player_name=excluded.player_name,
            damage=world_boss_damage.damage + excluded.damage,
            attack_count=world_boss_damage.attack_count + 1,
            updated_at=excluded.updated_at
        """,
        (boss_id, group_id, user_id, player_name, damage, 1, now),
    )


def list_damage(conn: sqlite3.Connection, boss_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT * FROM world_boss_damage
        WHERE boss_id=?
        ORDER BY damage DESC, updated_at ASC
        """,
        (boss_id,),
    ).fetchall()


def reward_exists(conn: sqlite3.Connection, boss_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM world_boss_rewards WHERE boss_id=? LIMIT 1",
        (boss_id,),
    ).fetchone()
    return row is not None


def record_reward(
    conn: sqlite3.Connection,
    boss_id: int,
    group_id: str,
    user_id: str,
    damage: int,
    damage_percent: float,
    gold: int,
    items_json: str,
    now: int,
) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO world_boss_rewards (
            boss_id,group_id,user_id,damage,damage_percent,gold,items_json,claimed_at
        ) VALUES (?,?,?,?,?,?,?,?)
        """,
        (boss_id, group_id, user_id, damage, damage_percent, gold, items_json, now),
    )
