from __future__ import annotations
import sqlite3

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
    created_at      INTEGER NOT NULL,
    last_active_at  INTEGER NOT NULL,
    UNIQUE(group_id, user_id)
);

CREATE TABLE IF NOT EXISTS inventory (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id   INTEGER NOT NULL REFERENCES players(id),
    item_id     TEXT NOT NULL,
    quantity    INTEGER NOT NULL DEFAULT 1,
    equipped    INTEGER NOT NULL DEFAULT 0
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
"""


def get_conn(path: str) -> sqlite3.Connection:
    # check_same_thread=False:允许连接在事件循环线程之外使用,避免将来新增同步处理器时
    # 触发 sqlite 的线程检查报错(写操作仍由 bot/state.py 的按玩家锁串行化)。
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")  # 改善读写并发(:memory: 下自动为 no-op)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
    migrate(conn)


def migrate(conn: sqlite3.Connection) -> None:
    """升级旧存档：建 buffs 表 + 迁移旧物品 ID。

    旧 ID 映射（有序，先迁 iron_sword 避免冲突）：
      iron_sword（精铁长剑）→ fine_steel_sword（百炼钢剑）
      rusty_sword（生锈的铁剑）→ iron_sword（铁剑）
    """
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

    # 迁移旧物品 ID（有序——先迁 iron_sword 以免与新 iron_sword 冲突）
    conn.execute(
        "UPDATE inventory SET item_id='fine_steel_sword' "
        "WHERE item_id='iron_sword'")
    conn.execute(
        "UPDATE inventory SET item_id='iron_sword' "
        "WHERE item_id='rusty_sword'")
    conn.commit()
