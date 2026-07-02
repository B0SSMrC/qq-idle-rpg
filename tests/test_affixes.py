import random

from game_core.affixes import (
    format_affix,
    modifiers,
    roll_affix,
)


def test_roll_weapon_affix_can_produce_lifesteal():
    seen = []
    for seed in range(200):
        affix = roll_affix("weapon", random.Random(seed))
        seen.append(format_affix(affix))
    assert any("嗜血" in text and "吸血" in text for text in seen)


def test_roll_affix_values_stay_in_expected_bounds():
    for slot in ("weapon", "armor"):
        for seed in range(200):
            affix = roll_affix(slot, random.Random(seed))
            for value in modifiers(affix).values():
                assert -0.15 <= value <= 0.20


def test_format_affix_describes_mixed_effects():
    text = format_affix('{"name":"狂战","effects":{"atk_pct":0.2,"def_pct":-0.15}}')
    assert "狂战" in text
    assert "攻击+20%" in text
    assert "防御-15%" in text
