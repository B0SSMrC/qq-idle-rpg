from __future__ import annotations

import re


_QUANTITY_RE = re.compile(r"^(.+?)(?:\s+[*×xX]?\s*|[*×xX]\s*)(\d+)$")


def parse_item_quantity(raw: str) -> tuple[str, int]:
    text = raw.strip()
    match = _QUANTITY_RE.match(text)
    if not match:
        return text, 1

    item_name = match.group(1).strip()
    quantity = int(match.group(2))
    if quantity <= 0:
        raise ValueError("数量必须大于 0")
    return item_name, quantity


def parse_travel_explore_arg(raw: str) -> str:
    text = raw.strip()
    suffix = "并探索"
    if not text.endswith(suffix):
        raise ValueError("用法: 回到 层数 并探索，例如「回到 35 并探索」")
    depth_query = text.removesuffix(suffix).strip()
    if not depth_query:
        raise ValueError("用法: 回到 层数 并探索，例如「回到 35 并探索」")
    return depth_query
