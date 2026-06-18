import random
from pathlib import Path
from storage.db import get_conn, init_db
from storage import repository as repo
from game_core.config import load_config
from app.services import register, do_explore, get_ranking
from bot.formatting import render_explore, render_status, render_ranking

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CFG = load_config(DATA_DIR)


def test_two_players_full_flow_with_persistence():
    conn = get_conn(":memory:")
    init_db(conn)
    rng = random.Random(7)
    register(conn, CFG, "g", "u1", "小明", now=0)
    register(conn, CFG, "g", "u2", "小红", now=0)

    # 各挂机 3 小时各探索一次,落库
    for u in ("u1", "u2"):
        res = do_explore(conn, CFG, "g", u, now=3 * 3600, rng=rng)
        text = render_explore(repo.get_player(conn, "g", u), res, CFG)
        assert "下潜" in text

    ranked = get_ranking(conn, CFG, "g", key="level")
    assert len(ranked) == 2
    assert "本群" in render_ranking(ranked, CFG, key="level")
    assert "小明" in render_status(repo.get_player(conn, "g", "u1"), CFG)
