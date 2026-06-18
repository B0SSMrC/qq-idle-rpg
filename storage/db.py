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
