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
    from storage.db import init_db
    init_db(conn)
    # 手动插入带旧 ID 的背包记录
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

    # 执行迁移
    from storage.db import migrate
    migrate(conn)

    # 验证迁移结果
    rows = conn.execute(
        "SELECT item_id FROM inventory WHERE player_id=?", (pid,)).fetchall()
    ids = {r["item_id"] for r in rows}
    assert ids == {"iron_sword", "fine_steel_sword"}


def test_init_db_creates_buffs_table():
    """buffs 表应在 init_db 后存在。"""
    conn = get_conn(":memory:")
    init_db(conn)
    names = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "buffs" in names
