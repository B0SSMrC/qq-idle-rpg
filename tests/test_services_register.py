import pytest
from pathlib import Path
from storage.db import get_conn, init_db
from game_core.config import load_config
from game_core.stats import hp_max
from game_core.errors import DuplicateName, CharacterNotFound
from app.services import register, status

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CFG = load_config(DATA_DIR)


def _conn():
    conn = get_conn(":memory:")
    init_db(conn)
    return conn


def test_register_creates_full_hp_character():
    conn = _conn()
    p = register(conn, CFG, "g", "u", "小明", now=1000)
    assert p.id is not None
    assert p.name == "小明"
    assert p.current_hp == hp_max(p, CFG)
    assert p.stamina_at == 1000


def test_register_duplicate_name_in_group_rejected():
    conn = _conn()
    register(conn, CFG, "g", "u1", "小明", now=0)
    with pytest.raises(DuplicateName):
        register(conn, CFG, "g", "u2", "小明", now=0)


def test_same_user_cannot_register_twice():
    conn = _conn()
    register(conn, CFG, "g", "u1", "小明", now=0)
    with pytest.raises(DuplicateName):
        register(conn, CFG, "g", "u1", "小红", now=0)


def test_status_settles_stamina_and_persists():
    conn = _conn()
    register(conn, CFG, "g", "u", "小明", now=0)
    b = CFG.balance
    expect = min(b.stamina_max, (60 // b.stamina_regen_minutes) * b.stamina_regen_amount)
    # 过 60 分钟后查状态,应已按配置结算出体力
    p = status(conn, CFG, "g", "u", now=60 * 60)
    assert p.stamina == expect
    # 再查一次(同一时刻)不应继续增长
    p2 = status(conn, CFG, "g", "u", now=60 * 60)
    assert p2.stamina == expect


def test_status_missing_character_raises():
    conn = _conn()
    with pytest.raises(CharacterNotFound):
        status(conn, CFG, "g", "nobody", now=0)
