from __future__ import annotations

import sqlite3

from game_core.void_sacrifice import VoidSacrificePity


def get_pity(conn: sqlite3.Connection, group_id: str, user_id: str) -> VoidSacrificePity:
    row = conn.execute(
        """
        SELECT * FROM void_sacrifice_pity
        WHERE group_id=? AND user_id=?
        """,
        (group_id, user_id),
    ).fetchone()
    if row is None:
        return VoidSacrificePity()
    return VoidSacrificePity(
        total_draws=int(row["total_draws"]),
        draws_since_mythic_plus=int(row["draws_since_mythic_plus"]),
        draws_since_divine=int(row["draws_since_divine"]),
    )


def save_pity(
    conn: sqlite3.Connection,
    group_id: str,
    user_id: str,
    pity: VoidSacrificePity,
    now: int,
) -> None:
    conn.execute(
        """
        INSERT INTO void_sacrifice_pity (
            group_id,user_id,total_draws,draws_since_mythic_plus,draws_since_divine,updated_at
        ) VALUES (?,?,?,?,?,?)
        ON CONFLICT(group_id, user_id) DO UPDATE SET
            total_draws=excluded.total_draws,
            draws_since_mythic_plus=excluded.draws_since_mythic_plus,
            draws_since_divine=excluded.draws_since_divine,
            updated_at=excluded.updated_at
        """,
        (
            group_id,
            user_id,
            pity.total_draws,
            pity.draws_since_mythic_plus,
            pity.draws_since_divine,
            now,
        ),
    )
