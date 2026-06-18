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
