from storage.db import get_conn, init_db
from storage.repository import (
    get_player, create_player, save_player, list_group_players,
)
from game_core.models import Player, InventoryItem


def _conn():
    conn = get_conn(":memory:")
    init_db(conn)
    return conn


def _player(group="g", user="u", name="勇者"):
    return Player(group_id=group, user_id=user, name=name,
                  stamina_at=0, current_hp=100, created_at=0, last_active_at=0)


def test_create_assigns_id_and_roundtrips():
    conn = _conn()
    p = create_player(conn, _player())
    assert p.id is not None
    loaded = get_player(conn, "g", "u")
    assert loaded is not None
    assert loaded.name == "勇者"
    assert loaded.current_hp == 100


def test_get_missing_returns_none():
    conn = _conn()
    assert get_player(conn, "g", "nobody") is None


def test_save_persists_changes_and_inventory():
    conn = _conn()
    p = create_player(conn, _player())
    p.level = 5
    p.gold = 123
    p.inventory.append(InventoryItem(item_id="rusty_sword", quantity=1, equipped=True))
    p.inventory.append(InventoryItem(item_id="hp_potion", quantity=3, equipped=False))
    save_player(conn, p)

    loaded = get_player(conn, "g", "u")
    assert loaded.level == 5
    assert loaded.gold == 123
    inv = {i.item_id: i for i in loaded.inventory}
    assert inv["rusty_sword"].equipped is True
    assert inv["hp_potion"].quantity == 3


def test_save_inventory_no_duplicates_on_resave():
    conn = _conn()
    p = create_player(conn, _player())
    p.inventory.append(InventoryItem(item_id="hp_potion", quantity=1))
    save_player(conn, p)
    save_player(conn, p)          # 再存一次不应翻倍
    loaded = get_player(conn, "g", "u")
    pots = [i for i in loaded.inventory if i.item_id == "hp_potion"]
    assert len(pots) == 1


def test_list_group_players_is_group_scoped():
    conn = _conn()
    create_player(conn, _player(group="g1", user="a", name="A"))
    create_player(conn, _player(group="g1", user="b", name="B"))
    create_player(conn, _player(group="g2", user="c", name="C"))
    g1 = list_group_players(conn, "g1")
    assert {p.name for p in g1} == {"A", "B"}
