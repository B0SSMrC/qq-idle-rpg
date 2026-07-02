from game_core.void_sacrifice import VoidSacrificePity
from storage import db, void_sacrifice_repo


def test_init_db_creates_void_sacrifice_pity_table():
    conn = db.get_conn(":memory:")
    db.init_db(conn)

    tables = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }

    assert "void_sacrifice_pity" in tables


def test_get_pity_returns_zero_state_before_first_draw():
    conn = db.get_conn(":memory:")
    db.init_db(conn)

    pity = void_sacrifice_repo.get_pity(conn, "g1", "u1")

    assert pity == VoidSacrificePity()


def test_save_pity_is_scoped_by_group_and_user():
    conn = db.get_conn(":memory:")
    db.init_db(conn)

    void_sacrifice_repo.save_pity(
        conn,
        "g1",
        "u1",
        VoidSacrificePity(total_draws=12, draws_since_mythic_plus=7, draws_since_divine=12),
        now=1000,
    )
    void_sacrifice_repo.save_pity(
        conn,
        "g2",
        "u1",
        VoidSacrificePity(total_draws=3, draws_since_mythic_plus=3, draws_since_divine=3),
        now=1001,
    )

    assert void_sacrifice_repo.get_pity(conn, "g1", "u1") == VoidSacrificePity(
        total_draws=12,
        draws_since_mythic_plus=7,
        draws_since_divine=12,
    )
    assert void_sacrifice_repo.get_pity(conn, "g2", "u1") == VoidSacrificePity(
        total_draws=3,
        draws_since_mythic_plus=3,
        draws_since_divine=3,
    )
