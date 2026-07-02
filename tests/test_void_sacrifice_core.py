from __future__ import annotations

import random
from pathlib import Path

import pytest

from game_core.config import load_config
from game_core.void_sacrifice import (
    DIVINE_PITY_THRESHOLD,
    MYTHIC_PLUS_PITY_THRESHOLD,
    VOID_SACRIFICE_SINGLE_COST,
    VOID_SACRIFICE_TEN_COST,
    VoidSacrificePity,
    parse_draw_count,
    remaining_divine_pity,
    remaining_mythic_plus_pity,
    roll_void_sacrifice,
)

CFG = load_config(Path("data"))


def test_void_sacrifice_constants_match_design():
    assert VOID_SACRIFICE_SINGLE_COST == 1000
    assert VOID_SACRIFICE_TEN_COST == 10000
    assert MYTHIC_PLUS_PITY_THRESHOLD == 50
    assert DIVINE_PITY_THRESHOLD == 120


@pytest.mark.parametrize(
    ("arg", "expected"),
    [
        ("", 1),
        ("1", 1),
        ("10", 10),
        ("\u5341\u8FDE\u732E\u796D", 10),
        ("\u732E\u796D\u5341\u8FDE", 10),
    ],
)
def test_parse_draw_count_accepts_supported_forms(arg, expected):
    assert parse_draw_count(arg) == expected


@pytest.mark.parametrize("arg", ["2", "11", "abc", "\u4e00", "\u4e00\u6b21", "\u5355\u62bd", "\u5341", "\u5341\u8FDE", "10\u8FDE"])
def test_parse_draw_count_rejects_unsupported_counts(arg):
    with pytest.raises(ValueError):
        parse_draw_count(arg)


def test_single_draw_can_return_rare_gear_with_affix_target():
    roll = roll_void_sacrifice(
        1,
        CFG,
        random.Random(5),
        VoidSacrificePity(),
    )

    assert len(roll.draws) == 1
    assert roll.draws[0].rarity in {
        "common",
        "rare",
        "epic",
        "legendary",
        "mythic",
        "divine",
    }
    if roll.draws[0].rarity != "common":
        assert roll.draws[0].item_id in CFG.items
        assert CFG.items[roll.draws[0].item_id].slot in {"weapon", "armor"}


def test_ten_draw_guarantees_epic_plus_when_all_rolls_are_low(monkeypatch):
    class LowRng(random.Random):
        def random(self):
            return 0.10

        def choice(self, seq):
            return seq[0]

        def randint(self, a, b):
            return a

    roll = roll_void_sacrifice(10, CFG, LowRng(), VoidSacrificePity())

    assert len(roll.draws) == 10
    assert roll.ten_draw_guarantee_triggered is True
    assert any(d.rarity in {"epic", "legendary", "mythic", "divine"} for d in roll.draws)
    assert roll.draws[-1].rarity == "epic"
    assert roll.draws[-1].guaranteed is True


def test_ten_draw_void_sacrifice_can_return_upgrade_materials():
    seen_material = False
    for seed in range(100):
        roll = roll_void_sacrifice(10, CFG, random.Random(seed), VoidSacrificePity())
        if any(
            draw.consumable_id in {"black_iron", "star_meteorite"}
            for draw in roll.draws
        ):
            seen_material = True
            break

    assert seen_material


def test_mythic_pity_forces_mythic_and_resets_mythic_counter():
    pity = VoidSacrificePity(
        total_draws=50,
        draws_since_mythic_plus=MYTHIC_PLUS_PITY_THRESHOLD,
        draws_since_divine=50,
    )

    roll = roll_void_sacrifice(1, CFG, random.Random(1), pity)

    assert roll.draws[0].rarity == "mythic"
    assert roll.draws[0].pity_trigger == "mythic"
    assert roll.pity.draws_since_mythic_plus == 0
    assert roll.pity.draws_since_divine == 51


def test_divine_pity_forces_divine_and_resets_both_counters():
    pity = VoidSacrificePity(
        total_draws=120,
        draws_since_mythic_plus=MYTHIC_PLUS_PITY_THRESHOLD,
        draws_since_divine=DIVINE_PITY_THRESHOLD,
    )

    roll = roll_void_sacrifice(1, CFG, random.Random(1), pity)

    assert roll.draws[0].rarity == "divine"
    assert roll.draws[0].pity_trigger == "divine"
    assert roll.pity.draws_since_mythic_plus == 0
    assert roll.pity.draws_since_divine == 0


def test_remaining_pity_counts_down_to_zero():
    pity = VoidSacrificePity(total_draws=0, draws_since_mythic_plus=37, draws_since_divine=112)

    assert remaining_mythic_plus_pity(pity) == 13
    assert remaining_divine_pity(pity) == 8
