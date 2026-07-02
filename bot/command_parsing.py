from __future__ import annotations

import re


_QUANTITY_RE = re.compile(r"^(.+?)(?:\s+[*×xX]?\s*|[*×xX]\s*)(\d+)$")
_QUANTITY_TOKEN_RE = re.compile(r"^[*×xX]?(\d+)$")


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


def parse_multi_item_quantities(raw: str) -> list[tuple[str, int]]:
    tokens = raw.strip().split()
    if not tokens:
        return []

    result: list[tuple[str, int]] = []
    for token in tokens:
        quantity_match = _QUANTITY_TOKEN_RE.match(token)
        if quantity_match:
            if not result:
                raise ValueError("数量前缺少物品名")
            quantity = int(quantity_match.group(1))
            if quantity <= 0:
                raise ValueError("数量必须大于 0")
            name, _ = result[-1]
            result[-1] = (name, quantity)
            continue

        item_name, quantity = parse_item_quantity(token)
        if not item_name:
            raise ValueError("用法:使用 物品名")
        result.append((item_name, quantity))
    return result


def parse_travel_explore_arg(raw: str) -> str:
    text = raw.strip()
    suffix = "并探索"
    if not text.endswith(suffix):
        raise ValueError("用法: 回到 层数 并探索，例如「回到 35 并探索」")
    depth_query = text.removesuffix(suffix).strip()
    if not depth_query:
        raise ValueError("用法: 回到 层数 并探索，例如「回到 35 并探索」")
    return depth_query
