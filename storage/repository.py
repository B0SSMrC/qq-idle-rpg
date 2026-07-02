from __future__ import annotations
import sqlite3
from game_core.models import Player, InventoryItem

PLAYER_COLS = [
    "group_id", "user_id", "name", "level", "exp", "gold", "stamina",
    "stamina_at", "current_hp", "current_depth", "max_depth",
    "stamina_refill_window_start", "stamina_refill_window_amount",
    "overdrive_until",
    "created_at", "last_active_at",
]


def _row_to_player(conn, row: sqlite3.Row, inv_rows: list[sqlite3.Row]) -> Player:
    p = Player(
        group_id=row["group_id"], user_id=row["user_id"], name=row["name"],
        level=row["level"], exp=row["exp"], gold=row["gold"],
        stamina=row["stamina"], stamina_at=row["stamina_at"],
        current_hp=row["current_hp"], current_depth=row["current_depth"],
        max_depth=row["max_depth"],
        stamina_refill_window_start=row["stamina_refill_window_start"],
        stamina_refill_window_amount=row["stamina_refill_window_amount"],
        overdrive_until=row["overdrive_until"],
        created_at=row["created_at"],
        last_active_at=row["last_active_at"], id=row["id"],
    )
    p.inventory = [
        InventoryItem(item_id=r["item_id"], quantity=r["quantity"],
                      equipped=bool(r["equipped"]), affix=r["affix"])
        for r in inv_rows
    ]
    p.buffs = _load_buffs(conn, row["id"])
    return p


def _load_buffs(conn: sqlite3.Connection, player_id: int) -> list:
    from game_core.models import Buff
    rows = conn.execute(
        "SELECT * FROM buffs WHERE player_id=?", (player_id,)).fetchall()
    return [Buff(type=r["type"], amount=r["amount"],
                 steps_left=r["steps_left"]) for r in rows]


def _save_buffs(conn: sqlite3.Connection, player) -> None:
    conn.execute("DELETE FROM buffs WHERE player_id=?", (player.id,))
    for b in player.buffs:
        conn.execute(
            "INSERT INTO buffs (player_id,type,amount,steps_left) "
            "VALUES (?,?,?,?)",
            (player.id, b.type, b.amount, b.steps_left))


def _load_inventory(conn: sqlite3.Connection, player_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM inventory WHERE player_id=?", (player_id,)).fetchall()


def get_player(conn: sqlite3.Connection, group_id: str, user_id: str) -> Player | None:
    row = conn.execute(
        "SELECT * FROM players WHERE group_id=? AND user_id=?",
        (group_id, user_id)).fetchone()
    if row is None:
        return None
    return _row_to_player(conn, row, _load_inventory(conn, row["id"]))


def create_player(conn: sqlite3.Connection, player: Player) -> Player:
    placeholders = ",".join("?" * len(PLAYER_COLS))
    cur = conn.execute(
        f"INSERT INTO players ({','.join(PLAYER_COLS)}) VALUES ({placeholders})",
        tuple(getattr(player, c) for c in PLAYER_COLS))
    player.id = cur.lastrowid
    _save_inventory(conn, player)
    _save_buffs(conn, player)
    conn.commit()
    return player


def save_player(conn: sqlite3.Connection, player: Player, *, commit: bool = True) -> None:
    set_clause = ",".join(f"{c}=?" for c in PLAYER_COLS)
    conn.execute(
        f"UPDATE players SET {set_clause} WHERE id=?",
        (*[getattr(player, c) for c in PLAYER_COLS], player.id))
    _save_inventory(conn, player)
    _save_buffs(conn, player)
    if commit:
        conn.commit()


def _save_inventory(conn: sqlite3.Connection, player: Player) -> None:
    # 背包条目很少,采用"删旧插新"保证与内存状态一致
    conn.execute("DELETE FROM inventory WHERE player_id=?", (player.id,))
    for it in player.inventory:
        conn.execute(
            "INSERT INTO inventory (player_id,item_id,quantity,equipped,affix) "
            "VALUES (?,?,?,?,?)",
            (player.id, it.item_id, it.quantity, int(it.equipped), it.affix))


def list_group_players(conn: sqlite3.Connection, group_id: str) -> list[Player]:
    rows = conn.execute(
        "SELECT * FROM players WHERE group_id=?", (group_id,)).fetchall()
    return [_row_to_player(conn, r, _load_inventory(conn, r["id"])) for r in rows]
