from bot.fuzzy_commands import ParsedCommand, parse_fuzzy_command


def assert_parsed(raw: str, command: str, arg: str = "", matched_alias: str | None = None):
    parsed = parse_fuzzy_command(raw)
    assert parsed is not None
    assert isinstance(parsed, ParsedCommand)
    assert parsed.command == command
    assert parsed.arg == arg
    assert parsed.confidence > 0.0
    if matched_alias is not None:
        assert parsed.matched_alias == matched_alias
    return parsed


def test_parsed_command_shape():
    parsed = ParsedCommand(
        command="explore",
        arg="",
        confidence=1.0,
        matched_alias="探索",
    )

    assert parsed.command == "explore"
    assert parsed.arg == ""
    assert parsed.confidence == 1.0
    assert parsed.matched_alias == "探索"


def test_all_standard_commands_are_supported():
    cases = [
        ("注册 小明", "register", "小明"),
        ("探索", "explore", ""),
        ("状态", "status", ""),
        ("背包", "inventory", ""),
        ("装备 铁剑", "equip", "铁剑"),
        ("购买装备 铁剑", "buy_equip", "铁剑"),
        ("卸下 铁剑", "unequip", "铁剑"),
        ("使用 金疮药", "use", "金疮药"),
        ("回满生命", "refill_hp", ""),
        ("回满体力", "refill_stamina", ""),
        ("重铸 武器", "reforge", "武器"),
        ("商店", "shop", ""),
        ("购买 金疮药", "buy", "金疮药"),
        ("出售装备", "sell_gear", ""),
        ("前往 35", "travel", "35"),
        ("回到 35 并探索", "travel_explore", "35 并探索"),
        ("排行榜", "ranking", ""),
        ("帮助", "help", ""),
        ("世界boss", "world_boss_status", ""),
        ("进攻世界boss", "world_boss_attack", ""),
        ("世界boss排行", "world_boss_ranking", ""),
    ]

    for raw, command, arg in cases:
        assert_parsed(raw, command, arg)


def test_slash_prefix_and_extra_spaces_are_accepted():
    assert_parsed("/  重铸　装备   10  ", "reforge", "装备 10", "重铸")
    assert_parsed(" /排行榜　深度 ", "ranking", "深度", "排行榜")


def test_required_compact_and_natural_phrases():
    cases = [
        ("重铸武器", "reforge", "武器"),
        ("重铸武器10", "reforge", "武器 10"),
        ("重铸 装备 10", "reforge", "装备 10"),
        ("查看背包", "inventory", ""),
        ("看看状态", "status", ""),
        ("打开商店", "shop", ""),
        ("买铁剑", "buy", "铁剑"),
        ("买装备铁剑", "buy_equip", "铁剑"),
        ("购买装备铁剑", "buy_equip", "铁剑"),
        ("使用金疮药3", "use", "金疮药 3"),
        ("回到35并探索", "travel_explore", "35 并探索"),
        ("回到 35 并 探索", "travel_explore", "35 并探索"),
        ("去35层", "travel", "35"),
        ("去 35 层", "travel", "35"),
        ("排行榜深度", "ranking", "深度"),
        ("帮助菜单", "help", ""),
    ]

    for raw, command, arg in cases:
        assert_parsed(raw, command, arg)


def test_more_natural_phrases_for_all_command_groups():
    cases = [
        ("注册角色小明", "register", "小明"),
        ("继续探索", "explore", ""),
        ("查看属性", "status", ""),
        ("看背包", "inventory", ""),
        ("穿戴铁剑", "equip", "铁剑"),
        ("取下铁剑", "unequip", "铁剑"),
        ("用金疮药3", "use", "金疮药 3"),
        ("补血", "refill_hp", ""),
        ("看商店", "shop", ""),
        ("回35层", "travel", "35"),
        ("查看排行榜", "ranking", ""),
        ("深度排行", "ranking", "深度"),
        ("指令菜单", "help", ""),
        ("boss状态", "world_boss_status", ""),
        ("打世界boss", "world_boss_attack", ""),
        ("进攻boss", "world_boss_attack", ""),
        ("boss排行", "world_boss_ranking", ""),
    ]

    for raw, command, arg in cases:
        assert_parsed(raw, command, arg)


def test_buy_and_buy_equip_are_not_confused():
    assert_parsed("购买铁剑", "buy", "铁剑", "购买")
    assert_parsed("买铁剑", "buy", "铁剑", "买")
    assert_parsed("购买装备铁剑", "buy_equip", "铁剑", "购买装备")
    assert_parsed("买装备铁剑", "buy_equip", "铁剑", "买装备")


def test_sell_gear_requires_safe_explicit_phrase():
    assert parse_fuzzy_command("装备") is not None
    assert parse_fuzzy_command("装备").command == "equip"
    assert parse_fuzzy_command("清理装备") is not None
    assert parse_fuzzy_command("清理装备").command == "sell_gear"
    assert parse_fuzzy_command("装备铁剑").command == "equip"
    assert parse_fuzzy_command("出售") is None
    assert parse_fuzzy_command("出售 铁剑") is None
    assert parse_fuzzy_command("出售装备铁剑") is None


def test_low_confidence_inputs_do_not_match():
    for raw in [
        "",
        "   ",
        "/",
        "体力",
        "查看体力",
        "装备在哪里",
        "购买装备",
        "出售装",
        "买不买铁剑",
        "去不去35层",
        "重铸一下武器",
        "我觉得状态不错",
        "boss在哪里",
    ]:
        assert parse_fuzzy_command(raw) is None


def test_fuzzy_void_sacrifice_aliases():
    assert parse_fuzzy_command("虚空献祭").command == "void_sacrifice"
    assert parse_fuzzy_command("献祭").command == "void_sacrifice"
    assert parse_fuzzy_command("虚空献祭10").arg == "10"
    assert parse_fuzzy_command("十连献祭").arg == "10"
