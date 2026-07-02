from bot import formatting
from bot import reply_templates as templates


def test_reply_template_pools_are_rich_enough():
    assert len(templates.COMBAT_WIN_TEMPLATES) >= 12
    assert len(templates.COMBAT_DEFEAT_TEMPLATES) >= 8
    assert len(templates.TREASURE_TEMPLATES) >= 8
    assert len(templates.TRAP_TEMPLATES) >= 8
    assert len(templates.LEVEL_UP_TEMPLATES) >= 6
    assert len(templates.EXPLORE_DEFEATED_FOOTERS) >= 6
    assert len(templates.STAMINA_EMPTY_FOOTERS) >= 6
    assert len(templates.EMPTY_INVENTORY_TEMPLATES) >= 8
    assert len(templates.EMPTY_SELL_TEMPLATES) >= 8
    assert len(templates.NO_WORLD_BOSS_TEMPLATES) >= 8
    assert len(templates.UNKNOWN_COMMAND_REPLIES) >= 25


def test_reply_templates_keep_required_format_fields():
    templates.COMBAT_WIN_TEMPLATES[0].format(
        depth=1, monster="monster", rounds=2, exp=3, gold=4, extra=""
    )
    templates.COMBAT_DEFEAT_TEMPLATES[0].format(depth=1, monster="monster")
    templates.TREASURE_TEMPLATES[0].format(depth=1, gold=2)
    templates.TRAP_TEMPLATES[0].format(depth=1, text="trap")
    templates.LEVEL_UP_TEMPLATES[0].format(level_ups=1, level=2)


def test_reply_templates_keep_stable_keywords_for_existing_outputs():
    assert all("空" in text for text in templates.EMPTY_INVENTORY_TEMPLATES)
    assert all("升级" in text for text in templates.LEVEL_UP_TEMPLATES)
    assert all(
        "回城" in text or "重伤" in text
        for text in templates.COMBAT_DEFEAT_TEMPLATES
    )


def test_formatting_uses_central_reply_template_pools():
    assert formatting.COMBAT_WIN_TEMPLATES is templates.COMBAT_WIN_TEMPLATES
