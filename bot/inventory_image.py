from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from game_core.affixes import format_affix
from game_core.models import GameConfig, InventoryItem, ItemDef, Player


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INVENTORY_IMAGE_DIR = PROJECT_ROOT / "runtime" / "inventory_images"

PAGE_WIDTH = 1200
PAGE_PADDING = 36
MAX_ROWS_PER_IMAGE = 45
ROW_HEIGHT = 42
HEADER_HEIGHT = 44
SECTION_TITLE_HEIGHT = 42
FOOTER_HEIGHT = 34

BACKGROUND = "#f8fafc"
SURFACE = "#ffffff"
BORDER = "#d9e2ec"
TEXT = "#18212f"
MUTED = "#667085"
HEADER_BG = "#e8eef5"
SECTION_BG = "#213547"
SECTION_TEXT = "#ffffff"
ACCENT = "#0f8b8d"


@dataclass(frozen=True)
class InventoryImageRow:
    name: str
    quantity: str
    status: str
    stats: str
    affix: str = ""
    price: str = ""


@dataclass(frozen=True)
class InventoryImageSection:
    title: str
    display_title: str
    rows: list[InventoryImageRow]


def summarize_inventory_sections(
    player: Player, cfg: GameConfig
) -> list[InventoryImageSection]:
    groups: dict[str, list[InventoryImageRow]] = {
        "Weapons": [],
        "Armor": [],
        "Consumables": [],
    }
    for inv in player.inventory:
        item = cfg.items.get(inv.item_id)
        if item is None:
            groups["Consumables"].append(
                InventoryImageRow(
                    name=inv.item_id,
                    quantity=f"x{inv.quantity}",
                    status="",
                    stats="Unknown item",
                )
            )
            continue
        row = _row_for_item(inv, item)
        if item.slot == "weapon":
            groups["Weapons"].append(row)
        elif item.slot == "armor":
            groups["Armor"].append(row)
        else:
            groups["Consumables"].append(row)

    display_titles = {
        "Weapons": "◆ 武器",
        "Armor": "◆ 装备",
        "Consumables": "◆ 消耗品",
    }
    return [
        InventoryImageSection(key, display_titles[key], rows)
        for key, rows in groups.items()
        if rows
    ]


def render_inventory_images(
    player: Player,
    cfg: GameConfig,
    output_dir: Path = INVENTORY_IMAGE_DIR,
    *,
    now: int | None = None,
    max_rows_per_image: int = MAX_ROWS_PER_IMAGE,
) -> list[Path]:
    now = int(time.time()) if now is None else int(now)
    output_dir.mkdir(parents=True, exist_ok=True)

    sections = summarize_inventory_sections(player, cfg)
    pages = _paginate_sections(sections, max_rows_per_image)
    if not pages:
        pages = [[]]

    paths: list[Path] = []
    safe_group = _safe_filename_part(player.group_id)
    safe_user = _safe_filename_part(player.user_id)
    for index, page_sections in enumerate(pages, start=1):
        suffix = f"_{index}" if len(pages) > 1 else ""
        path = output_dir / f"inventory_{safe_group}_{safe_user}_{now}{suffix}.png"
        image = _draw_inventory_page(player, page_sections, index, len(pages))
        image.save(path, format="PNG")
        paths.append(path)
    return paths


def cleanup_inventory_images(
    output_dir: Path = INVENTORY_IMAGE_DIR,
    *,
    now: int | None = None,
    max_age_seconds: int = 24 * 60 * 60,
) -> None:
    if not output_dir.exists():
        return
    now = int(time.time()) if now is None else int(now)
    for path in output_dir.glob("inventory_*.png"):
        try:
            if now - int(path.stat().st_mtime) > max_age_seconds:
                path.unlink()
        except OSError:
            continue


def _row_for_item(inv: InventoryItem, item: ItemDef) -> InventoryImageRow:
    return InventoryImageRow(
        name=item.name,
        quantity=f"x{inv.quantity}",
        status="Equipped" if inv.equipped else "",
        stats=_item_stats(item),
        affix=format_affix(inv.affix),
        price=str(item.price) if item.price is not None else "-",
    )


def _item_stats(item: ItemDef) -> str:
    parts: list[str] = []
    if item.atk:
        parts.append(f"攻击 {item.atk:+d}")
    if item.defense:
        parts.append(f"防御 {item.defense:+d}")
    if item.hp:
        parts.append(f"生命 {item.hp:+d}")
    if item.heal:
        parts.append(f"回复 {item.heal}")
    if item.buff_type == "atk":
        parts.append(f"攻击 +{item.buff_value}/{item.buff_steps}步")
    elif item.buff_type == "def":
        parts.append(f"防御 +{item.buff_value}/{item.buff_steps}步")
    elif item.buff_type == "stamina":
        parts.append(f"体力 +{item.buff_value}")
    return "  ".join(parts) if parts else "-"


def _paginate_sections(
    sections: list[InventoryImageSection], max_rows: int
) -> list[list[InventoryImageSection]]:
    pages: list[list[InventoryImageSection]] = []
    current: list[InventoryImageSection] = []
    current_rows = 0

    for section in sections:
        pending_rows = list(section.rows)
        while pending_rows:
            available = max_rows - current_rows
            if available <= 0:
                pages.append(current)
                current = []
                current_rows = 0
                available = max_rows
            chunk = pending_rows[:available]
            pending_rows = pending_rows[available:]
            current.append(
                InventoryImageSection(section.title, section.display_title, chunk)
            )
            current_rows += len(chunk)
            if pending_rows:
                pages.append(current)
                current = []
                current_rows = 0

    if current:
        pages.append(current)
    return pages


def _draw_inventory_page(
    player: Player,
    sections: list[InventoryImageSection],
    page_index: int,
    page_count: int,
) -> Image.Image:
    title_font = _load_font(34, bold=True)
    subtitle_font = _load_font(18)
    section_font = _load_font(22, bold=True)
    header_font = _load_font(17, bold=True)
    cell_font = _load_font(17)
    small_font = _load_font(15)

    row_count = sum(len(section.rows) for section in sections)
    section_count = len(sections)
    height = (
        PAGE_PADDING * 2
        + 50
        + 32
        + section_count * (SECTION_TITLE_HEIGHT + HEADER_HEIGHT + 12)
        + row_count * ROW_HEIGHT
        + FOOTER_HEIGHT
    )
    image = Image.new("RGB", (PAGE_WIDTH, max(360, height)), BACKGROUND)
    draw = ImageDraw.Draw(image)

    y = PAGE_PADDING
    draw.text((PAGE_PADDING, y), f"{player.name} 的背包", fill=TEXT, font=title_font)
    y += 46
    page_text = f"第 {page_index}/{page_count} 页" if page_count > 1 else "全部物品"
    subtitle = f"金币 {player.gold}    最深第 {player.max_depth} 层    {page_text}"
    draw.text((PAGE_PADDING, y), subtitle, fill=MUTED, font=subtitle_font)
    y += 34

    if not sections:
        _rounded_rect(draw, (PAGE_PADDING, y, PAGE_WIDTH - PAGE_PADDING, y + 120), SURFACE)
        draw.text((PAGE_PADDING + 28, y + 44), "背包还是空的", fill=MUTED, font=section_font)
        return image

    for section in sections:
        y = _draw_section(draw, y, section, section_font, header_font, cell_font)
        y += 12

    footer = "按类别整理：武器 / 装备 / 消耗品"
    draw.text((PAGE_PADDING, image.height - PAGE_PADDING), footer, fill=MUTED, font=small_font)
    return image


def _draw_section(
    draw: ImageDraw.ImageDraw,
    y: int,
    section: InventoryImageSection,
    section_font: ImageFont.ImageFont,
    header_font: ImageFont.ImageFont,
    cell_font: ImageFont.ImageFont,
) -> int:
    left = PAGE_PADDING
    right = PAGE_WIDTH - PAGE_PADDING
    width = right - left
    columns = [
        ("名称", 270),
        ("数量", 90),
        ("状态", 110),
        ("属性/效果", 310),
        ("词条", 270),
        ("价格", width - 270 - 90 - 110 - 310 - 270),
    ]

    _rounded_rect(draw, (left, y, right, y + SECTION_TITLE_HEIGHT), SECTION_BG)
    draw.text((left + 18, y + 9), section.display_title, fill=SECTION_TEXT, font=section_font)
    y += SECTION_TITLE_HEIGHT

    _rounded_rect(draw, (left, y, right, y + HEADER_HEIGHT), HEADER_BG)
    x = left
    for header, col_width in columns:
        draw.text((x + 12, y + 12), header, fill=TEXT, font=header_font)
        x += col_width
    y += HEADER_HEIGHT

    for row_index, row in enumerate(section.rows):
        fill = SURFACE if row_index % 2 == 0 else "#f1f5f9"
        draw.rectangle((left, y, right, y + ROW_HEIGHT), fill=fill)
        values = [
            row.name,
            row.quantity,
            "已装备" if row.status == "Equipped" else "-",
            row.stats,
            row.affix or "-",
            row.price,
        ]
        x = left
        for value, (_, col_width) in zip(values, columns):
            color = ACCENT if value == "已装备" else TEXT
            draw.text(
                (x + 12, y + 11),
                _fit_text(draw, value, cell_font, col_width - 24),
                fill=color,
                font=cell_font,
            )
            x += col_width
        draw.line((left, y + ROW_HEIGHT, right, y + ROW_HEIGHT), fill=BORDER)
        y += ROW_HEIGHT
    return y


def _fit_text(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int
) -> str:
    if _text_width(draw, text, font) <= max_width:
        return text
    ellipsis = "..."
    clipped = text
    while clipped and _text_width(draw, clipped + ellipsis, font) > max_width:
        clipped = clipped[:-1]
    return clipped + ellipsis if clipped else ellipsis


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _rounded_rect(
    draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: str
) -> None:
    draw.rounded_rectangle(box, radius=8, fill=fill, outline=BORDER, width=1)


def _load_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_names = [
        "msyhbd.ttc" if bold else "msyh.ttc",
        "simhei.ttf",
        "simsun.ttc",
        "arial.ttf",
    ]
    font_dirs = [
        Path("C:/Windows/Fonts"),
        Path("/usr/share/fonts/truetype/dejavu"),
        Path("/usr/share/fonts/opentype/noto"),
    ]
    for font_dir in font_dirs:
        for font_name in font_names:
            path = font_dir / font_name
            if path.exists():
                try:
                    return ImageFont.truetype(str(path), size=size)
                except OSError:
                    continue
    return ImageFont.load_default(size=size)


def _safe_filename_part(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value)
    return safe or "unknown"
