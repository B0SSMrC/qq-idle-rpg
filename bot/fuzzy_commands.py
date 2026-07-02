from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re


@dataclass(frozen=True)
class ParsedCommand:
    command: str
    arg: str
    confidence: float
    matched_alias: str


@dataclass(frozen=True)
class _AliasRule:
    command: str
    alias: str
    requires_arg: bool = False
    no_arg_only: bool = False
    fuzzy: bool = True
    fixed_arg: str = ""


_SPACE_RE = re.compile(r"[\s\u3000]+")
_TRAILING_NUMBER_RE = re.compile(r"^(.+?)(\d+)$")
_TRAVEL_EXPLORE_SUFFIX_RE = re.compile(r"^(.+?)(并探索)$")
_NUMERIC_LAYER_RE = re.compile(r"^(\d+)\s*层$")

_QUESTION_MARKERS = ("哪里", "在哪", "怎么", "如何", "吗", "么", "?", "？")

_RULES: tuple[_AliasRule, ...] = (
    _AliasRule("register", "注册角色", requires_arg=True),
    _AliasRule("register", "创建角色", requires_arg=True),
    _AliasRule("register", "注册", requires_arg=True),
    _AliasRule("register", "创建", requires_arg=True),
    _AliasRule("explore", "继续探索", no_arg_only=True),
    _AliasRule("explore", "继续冒险", no_arg_only=True),
    _AliasRule("explore", "探险", no_arg_only=True),
    _AliasRule("explore", "探索", no_arg_only=True),
    _AliasRule("explore", "下潜", no_arg_only=True),
    _AliasRule("explore", "冒险", no_arg_only=True),
    _AliasRule("status", "查看属性", no_arg_only=True),
    _AliasRule("status", "查看角色", no_arg_only=True),
    _AliasRule("status", "角色面板", no_arg_only=True),
    _AliasRule("status", "面板", no_arg_only=True),
    _AliasRule("status", "看看状态", no_arg_only=True),
    _AliasRule("status", "查看状态", no_arg_only=True),
    _AliasRule("status", "状态", no_arg_only=True),
    _AliasRule("status", "角色", no_arg_only=True),
    _AliasRule("status", "我", no_arg_only=True, fuzzy=False),
    _AliasRule("inventory", "看背包", no_arg_only=True),
    _AliasRule("inventory", "查看背包", no_arg_only=True),
    _AliasRule("inventory", "看看背包", no_arg_only=True),
    _AliasRule("inventory", "打开背包", no_arg_only=True),
    _AliasRule("inventory", "背包", no_arg_only=True),
    _AliasRule("inventory", "物品", no_arg_only=True),
    _AliasRule("buy_equip", "购买并装备", requires_arg=True),
    _AliasRule("buy_equip", "购买装备", requires_arg=True),
    _AliasRule("buy_equip", "购买武器", requires_arg=True),
    _AliasRule("buy_equip", "买装备", requires_arg=True),
    _AliasRule("buy_equip", "买武器", requires_arg=True),
    _AliasRule("equip", "穿戴"),
    _AliasRule("equip", "佩戴"),
    _AliasRule("unequip", "卸下"),
    _AliasRule("unequip", "脱下"),
    _AliasRule("unequip", "取下"),
    _AliasRule("refill_hp", "回满生命", no_arg_only=True),
    _AliasRule("refill_hp", "回满血", no_arg_only=True),
    _AliasRule("refill_hp", "补满生命", no_arg_only=True),
    _AliasRule("refill_hp", "补满血", no_arg_only=True),
    _AliasRule("refill_hp", "补血", no_arg_only=True),
    _AliasRule("refill_stamina", "回满体力", no_arg_only=True, fuzzy=False),
    _AliasRule("refill_stamina", "补满体力", no_arg_only=True, fuzzy=False),
    _AliasRule("reforge", "重铸", requires_arg=True, fuzzy=False),
    _AliasRule("shop", "看商店", no_arg_only=True),
    _AliasRule("shop", "打开商店", no_arg_only=True),
    _AliasRule("shop", "查看商店", no_arg_only=True),
    _AliasRule("shop", "商店", no_arg_only=True),
    _AliasRule("sell_gear", "出售装备", no_arg_only=True, fuzzy=False),
    _AliasRule("sell_gear", "一键出售", no_arg_only=True, fuzzy=False),
    _AliasRule("sell_gear", "清理装备", no_arg_only=True, fuzzy=False),
    _AliasRule("travel_explore", "回到", requires_arg=True, fuzzy=False),
    _AliasRule("travel", "前往", requires_arg=True),
    _AliasRule("travel", "回层", requires_arg=True),
    _AliasRule("travel", "去", requires_arg=True, fuzzy=False),
    _AliasRule("travel", "回", requires_arg=True, fuzzy=False),
    _AliasRule("ranking", "深度排行", no_arg_only=True, fixed_arg="深度"),
    _AliasRule("ranking", "深度榜", no_arg_only=True, fixed_arg="深度"),
    _AliasRule("ranking", "查看排行榜", no_arg_only=False),
    _AliasRule("ranking", "排行榜", no_arg_only=False),
    _AliasRule("ranking", "排名", no_arg_only=False),
    _AliasRule("help", "指令菜单", no_arg_only=True),
    _AliasRule("help", "帮助菜单", no_arg_only=True),
    _AliasRule("help", "帮助", no_arg_only=True),
    _AliasRule("help", "菜单", no_arg_only=True),
    _AliasRule("help", "?", no_arg_only=True, fuzzy=False),
    _AliasRule("world_boss_attack", "进攻世界boss", no_arg_only=True, fuzzy=False),
    _AliasRule("world_boss_attack", "攻击世界boss", no_arg_only=True, fuzzy=False),
    _AliasRule("world_boss_attack", "挑战世界boss", no_arg_only=True, fuzzy=False),
    _AliasRule("world_boss_attack", "打世界boss", no_arg_only=True, fuzzy=False),
    _AliasRule("world_boss_attack", "进攻boss", no_arg_only=True, fuzzy=False),
    _AliasRule("world_boss_ranking", "世界boss排行", no_arg_only=True),
    _AliasRule("world_boss_ranking", "boss排行", no_arg_only=True),
    _AliasRule("world_boss_status", "世界boss状态", no_arg_only=True),
    _AliasRule("world_boss_status", "boss状态", no_arg_only=True),
    _AliasRule("world_boss_status", "世界boss", no_arg_only=True),
    _AliasRule("equip", "装备"),
    _AliasRule("use", "使用", requires_arg=True),
    _AliasRule("use", "用", requires_arg=True, fuzzy=False),
    _AliasRule("buy", "购买", requires_arg=True),
    _AliasRule("buy", "买", requires_arg=True, fuzzy=False),
)


def _compact(text: str) -> str:
    return _SPACE_RE.sub("", text)


_ORDERED_RULES = tuple(
    sorted(_RULES, key=lambda r: len(_compact(r.alias)), reverse=True)
)


def parse_fuzzy_command(raw: str) -> ParsedCommand | None:
    text = _normalize(raw)
    if not text:
        return None

    compact_text = _compact(text)
    for rule in _ORDERED_RULES:
        parsed = _parse_by_rule(text, compact_text, rule)
        if parsed is not None:
            return parsed

    return _parse_fuzzy_no_arg(compact_text)


def _parse_by_rule(
    text: str, compact_text: str, rule: _AliasRule
) -> ParsedCommand | None:
    alias = _normalize(rule.alias)
    compact_alias = _compact(alias)

    if text.startswith(alias):
        arg = text[len(alias) :].strip()
        confidence = 1.0
    elif compact_text.startswith(compact_alias):
        arg = compact_text[len(compact_alias) :]
        confidence = 0.96
    else:
        return None

    arg = rule.fixed_arg or _normalize_arg(rule.command, arg)
    if not _is_allowed_arg(rule, compact_text, compact_alias, arg):
        return None

    return ParsedCommand(
        command=rule.command,
        arg=arg,
        confidence=confidence,
        matched_alias=rule.alias,
    )


def _parse_fuzzy_no_arg(compact_text: str) -> ParsedCommand | None:
    best_rule: _AliasRule | None = None
    best_score = 0.0

    for rule in _RULES:
        if not rule.no_arg_only or not rule.fuzzy:
            continue
        alias = _compact(rule.alias)
        if len(alias) < 2:
            continue
        score = SequenceMatcher(None, compact_text, alias).ratio()
        if score > best_score:
            best_score = score
            best_rule = rule

    if best_rule is None or best_score < 0.84:
        return None

    return ParsedCommand(
        command=best_rule.command,
        arg="",
        confidence=round(best_score, 3),
        matched_alias=best_rule.alias,
    )


def _is_allowed_arg(
    rule: _AliasRule, compact_text: str, compact_alias: str, arg: str
) -> bool:
    if rule.no_arg_only:
        return compact_text == compact_alias

    if rule.requires_arg and not arg:
        return False

    if rule.command == "travel_explore" and "并探索" not in arg:
        return False

    if rule.command == "buy" and arg in {"装备", "武器", "并装备"}:
        return False

    if rule.alias in {"买", "去", "回", "用"} and arg.startswith("不"):
        return False

    if rule.command == "reforge" and not arg.startswith(
        ("武器", "装备", "防具", "weapon", "armor")
    ):
        return False

    if arg and any(marker in arg for marker in _QUESTION_MARKERS):
        return False

    return True


def _normalize(raw: str) -> str:
    text = _SPACE_RE.sub(" ", raw.strip())
    if text.startswith("/"):
        text = text[1:].lstrip()
    return _SPACE_RE.sub(" ", text).strip()


def _normalize_arg(command: str, arg: str) -> str:
    arg = _SPACE_RE.sub(" ", arg.strip())
    if command in {"reforge", "use"}:
        match = _TRAILING_NUMBER_RE.match(arg)
        if match:
            arg = f"{match.group(1).strip()} {match.group(2)}"
    if command == "travel_explore":
        arg = re.sub(r"\s*并\s*探索$", " 并探索", arg)
        match = _TRAVEL_EXPLORE_SUFFIX_RE.match(arg)
        if match:
            target = _strip_numeric_layer(match.group(1).strip())
            arg = f"{target} {match.group(2)}"
    if command == "travel":
        arg = _strip_numeric_layer(arg)
    return arg


def _strip_numeric_layer(arg: str) -> str:
    match = _NUMERIC_LAYER_RE.match(arg)
    if match:
        return match.group(1)
    return arg
