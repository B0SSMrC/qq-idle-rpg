import pytest

from bot.command_parsing import (
    parse_item_quantity,
    parse_multi_item_quantities,
    parse_travel_explore_arg,
)


@pytest.mark.parametrize(
    ("raw", "expected_name", "expected_quantity"),
    [
        ("金疮药 3", "金疮药", 3),
        ("金疮药 *3", "金疮药", 3),
        ("金疮药 ×3", "金疮药", 3),
        ("金疮药", "金疮药", 1),
    ],
)
def test_parse_item_quantity(raw, expected_name, expected_quantity):
    name, quantity = parse_item_quantity(raw)
    assert name == expected_name
    assert quantity == expected_quantity


def test_parse_item_quantity_rejects_invalid_quantity():
    with pytest.raises(ValueError, match="数量必须大于 0"):
        parse_item_quantity("金疮药 0")


def test_parse_multi_item_quantities_supports_multiple_names():
    assert parse_multi_item_quantities("虎骨酒 蛮牛散") == [
        ("虎骨酒", 1),
        ("蛮牛散", 1),
    ]


def test_parse_multi_item_quantities_supports_quantity_tokens():
    assert parse_multi_item_quantities("金疮药 *3 虎骨酒") == [
        ("金疮药", 3),
        ("虎骨酒", 1),
    ]


def test_parse_multi_item_quantities_rejects_leading_quantity():
    with pytest.raises(ValueError, match="数量前缺少物品名"):
        parse_multi_item_quantities("*3 金疮药")


@pytest.mark.parametrize("raw", ["35 并探索", "35并探索", "最深 并探索"])
def test_parse_travel_explore_arg(raw):
    assert parse_travel_explore_arg(raw) in {"35", "最深"}


def test_parse_travel_explore_arg_rejects_missing_suffix():
    with pytest.raises(ValueError, match="用法"):
        parse_travel_explore_arg("35")
