from pathlib import Path
from storage.db import get_conn, init_db
from game_core.config import load_config
from mcp_server.handlers import player_view, h_register, h_status

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CFG = load_config(DATA_DIR)


def _conn():
    conn = get_conn(":memory:")
    init_db(conn)
    return conn


def test_register_returns_ok_and_player_view():
    conn = _conn()
    res = h_register(conn, CFG, "world1", "userA", "小明", now=0)
    assert res["ok"] is True
    p = res["player"]
    assert p["name"] == "小明"
    assert p["level"] == 1
    assert p["hp"] == p["hp_max"] == 100
    assert p["stamina"] == 0
    assert p["gold"] == 0
    assert p["depth"] == 1


def test_register_duplicate_name_returns_error():
    conn = _conn()
    h_register(conn, CFG, "w", "u1", "小明", now=0)
    res = h_register(conn, CFG, "w", "u2", "小明", now=0)
    assert res["ok"] is False
    assert "error" in res and res["error"]


def test_status_settles_stamina_by_real_time():
    conn = _conn()
    h_register(conn, CFG, "w", "u", "小明", now=0)
    b = CFG.balance
    expect = min(b.stamina_max, (60 // b.stamina_regen_minutes) * b.stamina_regen_amount)
    res = h_status(conn, CFG, "w", "u", now=60 * 60)
    assert res["ok"] is True
    assert res["player"]["stamina"] == expect


def test_status_missing_character_returns_error():
    conn = _conn()
    res = h_status(conn, CFG, "w", "nobody", now=0)
    assert res["ok"] is False
    assert "error" in res


def test_player_view_has_expected_fields():
    conn = _conn()
    res = h_register(conn, CFG, "w", "u", "勇者", now=0)
    p = res["player"]
    for key in ("name", "level", "exp", "exp_to_next", "hp", "hp_max",
                "stamina", "stamina_max", "atk", "def", "power",
                "gold", "depth", "max_depth", "equipped", "inventory"):
        assert key in p, f"missing field {key}"
    assert p["stamina_max"] == 50
    assert p["equipped"] == []
    assert p["inventory"] == []
