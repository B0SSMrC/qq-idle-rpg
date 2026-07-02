from storage.db import get_conn, init_db


def test_init_db_creates_tables():
    conn = get_conn(":memory:")
    init_db(conn)
    names = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "players" in names
    assert "inventory" in names


def test_players_unique_group_user():
    conn = get_conn(":memory:")
    init_db(conn)
    conn.execute("INSERT INTO players (group_id,user_id,name,stamina_at,current_hp,created_at,last_active_at) "
                 "VALUES ('g','u','勇者',0,100,0,0)")
    import sqlite3
    import pytest
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO players (group_id,user_id,name,stamina_at,current_hp,created_at,last_active_at) "
                     "VALUES ('g','u','另一个',0,100,0,0)")


def test_row_factory_returns_mapping():
    conn = get_conn(":memory:")
    init_db(conn)
    row = conn.execute("SELECT 1 AS x").fetchone()
    assert row["x"] == 1


def test_migrate_old_item_ids():
    """旧物品 ID 应被迁移为新 ID。"""
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    # 模拟扩展前旧库：有 players/inventory，但没有 buffs/schema_migrations。
    conn.executescript("""
        CREATE TABLE players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            level INTEGER NOT NULL DEFAULT 1,
            exp INTEGER NOT NULL DEFAULT 0,
            gold INTEGER NOT NULL DEFAULT 0,
            stamina INTEGER NOT NULL DEFAULT 0,
            stamina_at INTEGER NOT NULL,
            current_hp INTEGER NOT NULL,
            current_depth INTEGER NOT NULL DEFAULT 1,
            max_depth INTEGER NOT NULL DEFAULT 1,
            created_at INTEGER NOT NULL,
            last_active_at INTEGER NOT NULL,
            UNIQUE(group_id, user_id)
        );
        CREATE TABLE inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL REFERENCES players(id),
            item_id TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            equipped INTEGER NOT NULL DEFAULT 0
        );
    """)
    conn.execute(
        "INSERT INTO players (group_id,user_id,name,stamina_at,current_hp,created_at,last_active_at) "
        "VALUES ('g','u','test',0,100,0,0)")
    pid = conn.execute("SELECT id FROM players WHERE user_id='u'").fetchone()["id"]
    conn.execute(
        "INSERT INTO inventory (player_id,item_id,quantity) VALUES (?,?,?)",
        (pid, "rusty_sword", 1))
    conn.execute(
        "INSERT INTO inventory (player_id,item_id,quantity) VALUES (?,?,?)",
        (pid, "iron_sword", 1))
    conn.commit()

    # 执行完整初始化；init_db 会识别这是旧库并只迁移一次。
    from storage.db import init_db
    init_db(conn)

    # 验证迁移结果
    rows = conn.execute(
        "SELECT item_id FROM inventory WHERE player_id=?", (pid,)).fetchall()
    ids = {r["item_id"] for r in rows}
    assert ids == {"iron_sword", "fine_steel_sword"}


def test_legacy_item_migration_is_idempotent():
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    from storage.db import init_db
    init_db(conn)
    conn.execute(
        "INSERT INTO players (group_id,user_id,name,stamina_at,current_hp,created_at,last_active_at) "
        "VALUES ('g','u','test',0,100,0,0)")
    pid = conn.execute("SELECT id FROM players WHERE user_id='u'").fetchone()["id"]
    conn.execute(
        "INSERT INTO inventory (player_id,item_id,quantity) VALUES (?,?,?)",
        (pid, "iron_sword", 1))
    conn.commit()

    init_db(conn)

    item_id = conn.execute(
        "SELECT item_id FROM inventory WHERE player_id=?", (pid,)
    ).fetchone()["item_id"]
    assert item_id == "iron_sword"


def test_players_unique_group_name():
    import sqlite3
    conn = get_conn(":memory:")
    init_db(conn)
    conn.execute(
        "INSERT INTO players (group_id,user_id,name,stamina_at,current_hp,created_at,last_active_at) "
        "VALUES ('g','u1','勇者',0,100,0,0)")
    import pytest
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO players (group_id,user_id,name,stamina_at,current_hp,created_at,last_active_at) "
            "VALUES ('g','u2','勇者',0,100,0,0)")


def test_init_db_creates_buffs_table():
    """buffs 表应在 init_db 后存在。"""
    conn = get_conn(":memory:")
    init_db(conn)
    names = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "buffs" in names


def test_init_db_adds_stamina_refill_columns_to_existing_players_table():
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            level INTEGER NOT NULL DEFAULT 1,
            exp INTEGER NOT NULL DEFAULT 0,
            gold INTEGER NOT NULL DEFAULT 0,
            stamina INTEGER NOT NULL DEFAULT 0,
            stamina_at INTEGER NOT NULL,
            current_hp INTEGER NOT NULL,
            current_depth INTEGER NOT NULL DEFAULT 1,
            max_depth INTEGER NOT NULL DEFAULT 1,
            created_at INTEGER NOT NULL,
            last_active_at INTEGER NOT NULL,
            UNIQUE(group_id, user_id)
        );
        CREATE TABLE inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL REFERENCES players(id),
            item_id TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            equipped INTEGER NOT NULL DEFAULT 0
        );
    """)
    init_db(conn)

    cols = {r["name"] for r in conn.execute("PRAGMA table_info(players)")}
    assert "stamina_refill_window_start" in cols
    assert "stamina_refill_window_amount" in cols
    assert "overdrive_until" in cols


def test_init_db_adds_inventory_affix_column_to_existing_inventory_table():
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            stamina_at INTEGER NOT NULL,
            current_hp INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            last_active_at INTEGER NOT NULL,
            UNIQUE(group_id, user_id)
        );
        CREATE TABLE inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL REFERENCES players(id),
            item_id TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            equipped INTEGER NOT NULL DEFAULT 0
        );
    """)
    init_db(conn)

    cols = {r["name"] for r in conn.execute("PRAGMA table_info(inventory)")}
    assert "affix" in cols
