import os
from pathlib import Path

from game_core.config import load_config
from game_core.models import InventoryItem, Player

from bot.inventory_image import (
    cleanup_inventory_images,
    render_inventory_images,
    summarize_inventory_sections,
)


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CFG = load_config(DATA_DIR)


def _player_with_inventory(items):
    player = Player(group_id="g", user_id="u", name="cxh", gold=100)
    player.inventory = items
    return player


def test_summarize_inventory_sections_groups_items_by_slot():
    player = _player_with_inventory(
        [
            InventoryItem(item_id="iron_sword", quantity=1, equipped=True),
            InventoryItem(item_id="cloth_armor", quantity=1),
            InventoryItem(item_id="hp_potion", quantity=3),
        ]
    )

    sections = summarize_inventory_sections(player, CFG)

    by_title = {section.title: section for section in sections}
    assert CFG.items["iron_sword"].name in by_title["Weapons"].rows[0].name
    assert by_title["Weapons"].rows[0].status == "Equipped"
    assert "+5" in by_title["Weapons"].rows[0].stats
    assert CFG.items["cloth_armor"].name in by_title["Armor"].rows[0].name
    assert "+2" in by_title["Armor"].rows[0].stats
    assert "+20" in by_title["Armor"].rows[0].stats
    assert CFG.items["hp_potion"].name in by_title["Consumables"].rows[0].name
    assert "x3" == by_title["Consumables"].rows[0].quantity
    assert "40" in by_title["Consumables"].rows[0].stats


def test_render_inventory_images_writes_png_file(tmp_path):
    player = _player_with_inventory(
        [
            InventoryItem(item_id="iron_sword", quantity=1, equipped=True),
            InventoryItem(item_id="hp_potion", quantity=3),
        ]
    )

    paths = render_inventory_images(player, CFG, tmp_path, now=1234567890)

    assert len(paths) == 1
    assert paths[0].exists()
    assert paths[0].suffix == ".png"
    assert paths[0].name.startswith("inventory_g_u_1234567890")
    assert paths[0].read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_render_inventory_images_paginates_large_inventory(tmp_path):
    player = _player_with_inventory(
        [InventoryItem(item_id="iron_sword", quantity=1) for _ in range(12)]
    )

    paths = render_inventory_images(
        player, CFG, tmp_path, now=1234567890, max_rows_per_image=5
    )

    assert len(paths) == 3
    assert all(path.exists() for path in paths)


def test_cleanup_inventory_images_removes_only_old_inventory_pngs(tmp_path):
    old_path = tmp_path / "inventory_g_u_old.png"
    fresh_path = tmp_path / "inventory_g_u_fresh.png"
    unrelated_path = tmp_path / "notes.txt"
    for path in (old_path, fresh_path, unrelated_path):
        path.write_text("x", encoding="utf-8")
    os.utime(old_path, (100, 100))
    os.utime(fresh_path, (1000, 1000))
    os.utime(unrelated_path, (100, 100))

    cleanup_inventory_images(tmp_path, now=1000, max_age_seconds=500)

    assert not old_path.exists()
    assert fresh_path.exists()
    assert unrelated_path.exists()
