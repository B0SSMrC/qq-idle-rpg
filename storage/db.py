from __future__ import annotations
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id        TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    name            TEXT NOT NULL,
    level           INTEGER NOT NULL DEFAULT 1,
    exp             INTEGER NOT NULL DEFAULT 0,
    gold            INTEGER NOT NULL DEFAULT 0,
    stamina         INTEGER NOT NULL DEFAULT 0,
    stamina_at      INTEGER NOT NULL,
    current_hp      INTEGER NOT NULL,
    current_depth   INTEGER NOT NULL DEFAULT 1,
    max_depth       INTEGER NOT NULL DEFAULT 1,
    stamina_refill_window_start INTEGER NOT NULL DEFAULT 0,
    stamina_refill_window_amount INTEGER NOT NULL DEFAULT 0,
    overdrive_until INTEGER NOT NULL DEFAULT 0,
    created_at      INTEGER NOT NULL,
    last_active_at  INTEGER NOT NULL,
    UNIQUE(group_id, user_id)
);

CREATE TABLE IF NOT EXISTS inventory (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id   INTEGER NOT NULL REFERENCES players(id),
    item_id     TEXT NOT NULL,
    quantity    INTEGER NOT NULL DEFAULT 1,
    equipped    INTEGER NOT NULL DEFAULT 0,
    affix       TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_inventory_player ON inventory(player_id);
CREATE INDEX IF NOT EXISTS idx_players_group ON players(group_id);

CREATE TABLE IF NOT EXISTS buffs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id   INTEGER NOT NULL REFERENCES players(id),
    type        TEXT NOT NULL,
    amount      INTEGER NOT NULL,
    steps_left  INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_buffs_player ON buffs(player_id);

CREATE TABLE IF NOT EXISTS schema_migrations (
    name        TEXT PRIMARY KEY,
    applied_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS world_bosses (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id              TEXT NOT NULL,
    boss_key              TEXT NOT NULL,
    name                  TEXT NOT NULL,
    hp_max                INTEGER NOT NULL,
    hp_current            INTEGER NOT NULL,
    atk                   INTEGER NOT NULL,
    def                   INTEGER NOT NULL,
    status                TEXT NOT NULL,
    version               INTEGER NOT NULL DEFAULT 0,
    spawned_at            INTEGER NOT NULL,
    expires_at            INTEGER NOT NULL,
    next_spawn_at         INTEGER NOT NULL DEFAULT 0,
    last_announcement_at  INTEGER NOT NULL DEFAULT 0,
    updated_at            INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_world_bosses_group_status
ON world_bosses(group_id, status);

CREATE TABLE IF NOT EXISTS world_boss_damage (
    boss_id       INTEGER NOT NULL REFERENCES world_bosses(id),
    group_id      TEXT NOT NULL,
    user_id       TEXT NOT NULL,
    player_name   TEXT NOT NULL,
    damage        INTEGER NOT NULL DEFAULT 0,
    attack_count  INTEGER NOT NULL DEFAULT 0,
    updated_at    INTEGER NOT NULL,
    PRIMARY KEY (boss_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_world_boss_damage_boss
ON world_boss_damage(boss_id, damage DESC);

CREATE TABLE IF NOT EXISTS world_boss_rewards (
    boss_id         INTEGER NOT NULL REFERENCES world_bosses(id),
    group_id        TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    damage          INTEGER NOT NULL,
    damage_percent  REAL NOT NULL,
    gold            INTEGER NOT NULL,
    items_json      TEXT NOT NULL DEFAULT '[]',
    claimed_at      INTEGER NOT NULL,
    PRIMARY KEY (boss_id, user_id)
);
"""

LEGACY_ITEM_ID_MIGRATION = "2026_06_18_legacy_item_ids"


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def get_conn(path: str) -> sqlite3.Connection:
    # check_same_thread=False:允许连接在事件循环线程之外使用,避免将来新增同步处理器时
    # 触发 sqlite 的线程检查报错(写操作仍由 bot/state.py 的按玩家锁串行化)。
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")  # 改善读写并发(:memory: 下自动为 no-op)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    had_players = _table_exists(conn, "players")
    had_buffs = _table_exists(conn, "buffs")
    conn.executescript(SCHEMA)
    conn.commit()
    migrate(conn, legacy_item_migration_needed=had_players and not had_buffs)


def _migration_applied(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM schema_migrations WHERE name=?", (name,)
    ).fetchone()
    return row is not None


def _mark_migration(conn: sqlite3.Connection, name: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations (name, applied_at) VALUES (?, ?)",
        (name, int(time.time())),
    )


def _ensure_unique_player_names(conn: sqlite3.Connection) -> None:
    duplicates = conn.execute(
        """
        SELECT group_id, name, COUNT(*) AS count
        FROM players
        GROUP BY group_id, name
        HAVING COUNT(*) > 1
        """
    ).fetchall()
    if duplicates:
        raise sqlite3.IntegrityError(
            "cannot create unique player-name index while duplicate names exist"
        )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_players_group_name_unique "
        "ON players(group_id, name)"
    )


def _ensure_player_columns(conn: sqlite3.Connection) -> None:
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(players)")}
    additions = {
        "stamina_refill_window_start": "INTEGER NOT NULL DEFAULT 0",
        "stamina_refill_window_amount": "INTEGER NOT NULL DEFAULT 0",
        "overdrive_until": "INTEGER NOT NULL DEFAULT 0",
    }
    for name, ddl in additions.items():
        if name not in cols:
            conn.execute(f"ALTER TABLE players ADD COLUMN {name} {ddl}")


def _ensure_inventory_columns(conn: sqlite3.Connection) -> None:
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(inventory)")}
    if "affix" not in cols:
        conn.execute("ALTER TABLE inventory ADD COLUMN affix TEXT NOT NULL DEFAULT ''")


def migrate(conn: sqlite3.Connection, *, legacy_item_migration_needed: bool = False) -> None:
    """升级旧存档：建 buffs 表 + 迁移旧物品 ID。

    旧 ID 映射（有序，先迁 iron_sword 避免冲突）：
      iron_sword（精铁长剑）→ fine_steel_sword（百炼钢剑）
      rusty_sword（生锈的铁剑）→ iron_sword（铁剑）

    物品 ID 迁移只适用于扩展前旧库。新库里 iron_sword 已经表示“铁剑”，
    不能在每次启动时重复迁移。
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            name TEXT PRIMARY KEY,
            applied_at INTEGER NOT NULL
        )
    """)

    # 建 buffs 表（IF NOT EXISTS 已覆盖，显式保障）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS buffs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL REFERENCES players(id),
            type TEXT NOT NULL,
            amount INTEGER NOT NULL,
            steps_left INTEGER NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_buffs_player ON buffs(player_id)")

    _ensure_player_columns(conn)
    _ensure_inventory_columns(conn)

    if (legacy_item_migration_needed
            and not _migration_applied(conn, LEGACY_ITEM_ID_MIGRATION)):
        # 有序——先迁 iron_sword，以免与新 iron_sword 冲突。
        conn.execute(
            "UPDATE inventory SET item_id='fine_steel_sword' "
            "WHERE item_id='iron_sword'")
        conn.execute(
            "UPDATE inventory SET item_id='iron_sword' "
            "WHERE item_id='rusty_sword'")
    _mark_migration(conn, LEGACY_ITEM_ID_MIGRATION)

    _ensure_unique_player_names(conn)
    conn.commit()
