from __future__ import annotations
import asyncio
import time
from collections import defaultdict
from pathlib import Path
from game_core.config import load_config
from storage.db import get_conn, init_db

_BASE = Path(__file__).resolve().parent.parent
CFG = load_config(_BASE / "data")

_conn = get_conn(str(_BASE / "rpg.db"))
init_db(_conn)


def conn():
    return _conn


_locks: dict[tuple[str, str], asyncio.Lock] = defaultdict(asyncio.Lock)


def player_lock(group_id: str, user_id: str) -> asyncio.Lock:
    return _locks[(group_id, user_id)]


def now() -> int:
    return int(time.time())
