"""RPG command plugin for OneBot v11.

Identity mapping:
- Group chat: group_id = OneBot group_id, user_id = OneBot user_id
- Private chat: group_id = "private", user_id = OneBot user_id
"""
from __future__ import annotations

import asyncio
import random
from pathlib import Path

import nonebot
from nonebot import on_command, on_message
from nonebot.rule import to_me
from nonebot.adapters import Bot, Event

try:
    from nonebot.adapters.onebot.v11 import (
        GroupMessageEvent as OneBotGroupMessageEvent,
        MessageSegment,
        PrivateMessageEvent as OneBotPrivateMessageEvent,
    )
except ImportError:  # pragma: no cover - 取决于部署时启用的适配器
    OneBotGroupMessageEvent = OneBotPrivateMessageEvent = None
    MessageSegment = None

import bot.state as state
from app import services
from bot.command_parsing import parse_multi_item_quantities, parse_travel_explore_arg
from bot.fuzzy_commands import parse_fuzzy_command
from bot.formatting import (
    render_explore,
    render_status,
    render_ranking,
    render_shop,
    render_inventory,
    render_sell_result,
    render_dismantle_result,
    render_enhance_result,
    render_star_up_result,
    render_void_sacrifice,
    render_world_boss_attack,
    render_world_boss_status,
)
from bot.inventory_image import (
    INVENTORY_IMAGE_DIR,
    cleanup_inventory_images,
    render_inventory_images,
)
from bot.reply_templates import UNKNOWN_COMMAND_REPLIES
from game_core.affixes import format_affix
from game_core.errors import GameError
from game_core.void_sacrifice import parse_draw_count
from storage import repository as repo

logger = nonebot.log.logger
_world_boss_announcement_task: asyncio.Task | None = None


# ---------------------------------------------------------------------------
# 范围解析 / 通用工具
# ---------------------------------------------------------------------------


def _scope(event: Event) -> tuple[str, str]:
    """返回 (group_id, user_id):group_id 是排行榜/世界范围,因事件类型而异。"""
    uid = event.get_user_id()
    if OneBotGroupMessageEvent and isinstance(event, OneBotGroupMessageEvent):
        return str(event.group_id), str(event.user_id)
    if OneBotPrivateMessageEvent and isinstance(event, OneBotPrivateMessageEvent):
        return "private", str(event.user_id)
    return "unknown", uid


def _arg(event: Event, *cmd_words: str) -> str:
    """从消息纯文本里剥掉指令词,返回参数部分。"""
    text = event.get_plaintext().strip()
    for w in cmd_words:
        for prefix in ("", "/"):
            token = f"{prefix}{w}"
            if text.startswith(token):
                return text.removeprefix(token).strip()
    return text.strip()


async def _reply(bot: Bot, event: Event, text: str):
    return await bot.send(event, text)


async def _reply_to(bot: Bot, event: Event, name: str, text: str):
    """给回复加上角色名前缀，群聊里一眼看出在回复谁。"""
    return await bot.send(event, f"「{name}」\n{text}")


async def _reply_inventory(bot: Bot, event: Event, player):
    if MessageSegment is None:
        await _reply_to(bot, event, player.name, render_inventory(player, state.CFG))
        return
    try:
        output_dir = Path(INVENTORY_IMAGE_DIR)
        image_paths = render_inventory_images(player, state.CFG, output_dir, now=state.now())
        cleanup_inventory_images(output_dir, now=state.now())
        await _reply_to(bot, event, player.name, "背包已整理成图片：")
        for path in image_paths:
            await bot.send(event, MessageSegment.image(path.resolve().as_uri()))
    except Exception:
        logger.exception("背包图片发送失败，回退到文字背包")
        await _reply_to(bot, event, player.name, render_inventory(player, state.CFG))


async def _guard(bot: Bot, event: Event, coro):
    """统一守卫:GameError → 友好提示;其它异常 → 记日志 + 通用提示,绝不外泄堆栈。"""
    try:
        await coro
    except GameError as e:
        await _reply(bot, event, str(e))
    except Exception:
        logger.exception("RPG 指令处理异常")
        await _reply(bot, event, "⚠️ 出了点小问题,已记录,稍后再试~")


# ---------------------------------------------------------------------------
# 注册 / 创建
# ---------------------------------------------------------------------------

cmd_register = on_command("注册", aliases={"创建"}, rule=to_me(), priority=10, block=True)


async def _handle_register_name(bot: Bot, event: Event, name: str):
    if not name:
        await _reply(bot, event, "用法:注册 角色名(群里/频道里需 @机器人)")
        return
    gid, uid = _scope(event)

    async def _do():
        async with state.player_lock(gid, uid):
            p = services.register(state.conn(), state.CFG, gid, uid, name, state.now())
            await _reply_to(bot, event, p.name, "✅ 角色已创建!发「探索」开始冒险吧~")

    await _guard(bot, event, _do())


@cmd_register.handle()
async def handle_register(bot: Bot, event: Event):
    await _handle_register_name(bot, event, _arg(event, "注册", "创建"))


# ---------------------------------------------------------------------------
# 探索 / 下潜 / 冒险
# ---------------------------------------------------------------------------

cmd_explore = on_command("探索", aliases={"下潜", "冒险"}, rule=to_me(), priority=10, block=True)


@cmd_explore.handle()
async def handle_explore(bot: Bot, event: Event):
    gid, uid = _scope(event)

    async def _do():
        async with state.player_lock(gid, uid):
            res = services.do_explore(
                state.conn(), state.CFG, gid, uid, state.now(), random.Random()
            )
            p = repo.get_player(state.conn(), gid, uid)
            await _reply_to(bot, event, p.name, render_explore(p, res, state.CFG))

    await _guard(bot, event, _do())


# ---------------------------------------------------------------------------
# 状态 / 我 / 角色
# ---------------------------------------------------------------------------

cmd_status = on_command("状态", aliases={"我", "角色"}, rule=to_me(), priority=10, block=True)


@cmd_status.handle()
async def handle_status(bot: Bot, event: Event):
    gid, uid = _scope(event)

    async def _do():
        async with state.player_lock(gid, uid):
            p = services.status(state.conn(), state.CFG, gid, uid, state.now())
            await _reply_to(bot, event, p.name, render_status(p, state.CFG))

    await _guard(bot, event, _do())


# ---------------------------------------------------------------------------
# 背包 / 物品
# ---------------------------------------------------------------------------

cmd_inventory = on_command("背包", aliases={"物品"}, rule=to_me(), priority=10, block=True)


@cmd_inventory.handle()
async def handle_inventory(bot: Bot, event: Event):
    gid, uid = _scope(event)

    async def _do():
        async with state.player_lock(gid, uid):
            p = repo.get_player(state.conn(), gid, uid)
            if p is None:
                await _reply(bot, event, "你还没有角色,先发「注册 角色名」吧~")
                return
            await _reply_inventory(bot, event, p)

    await _guard(bot, event, _do())


# ---------------------------------------------------------------------------
# 装备
# ---------------------------------------------------------------------------

cmd_equip = on_command("装备", rule=to_me(), priority=10, block=True)


async def _handle_equip_item(bot: Bot, event: Event, item_query: str):
    if not item_query:
        await _reply(bot, event, "用法:装备 物品名")
        return
    gid, uid = _scope(event)

    async def _do():
        async with state.player_lock(gid, uid):
            p = services.do_equip(state.conn(), state.CFG, gid, uid, item_query)
            await _reply_to(bot, event, p.name, render_status(p, state.CFG))

    await _guard(bot, event, _do())


@cmd_equip.handle()
async def handle_equip(bot: Bot, event: Event):
    await _handle_equip_item(bot, event, _arg(event, "装备"))


# ---------------------------------------------------------------------------
# 购买并装备
# ---------------------------------------------------------------------------

cmd_buy_equip = on_command(
    "购买装备",
    aliases={"购买武器", "购买并装备", "买装备", "买武器"},
    rule=to_me(),
    priority=10,
    block=True,
)


async def _handle_buy_equip_item(bot: Bot, event: Event, item_query: str):
    if not item_query:
        await _reply(bot, event, "用法:购买装备 物品名")
        return
    gid, uid = _scope(event)

    async def _do():
        async with state.player_lock(gid, uid):
            result = services.do_buy_and_equip(state.conn(), state.CFG, gid, uid, item_query)
            text = (
                f"✅ 已购买并装备【{result.item_name}】,花费{result.cost}金币。\n"
                + render_status(result.player, state.CFG)
            )
            await _reply_to(bot, event, result.player.name, text)

    await _guard(bot, event, _do())


@cmd_buy_equip.handle()
async def handle_buy_equip(bot: Bot, event: Event):
    await _handle_buy_equip_item(
        bot, event, _arg(event, "购买装备", "购买武器", "购买并装备", "买装备", "买武器")
    )


# ---------------------------------------------------------------------------
# 卸下
# ---------------------------------------------------------------------------

cmd_unequip = on_command("卸下", rule=to_me(), priority=10, block=True)


async def _handle_unequip_item(bot: Bot, event: Event, item_query: str):
    if not item_query:
        await _reply(bot, event, "用法:卸下 物品名")
        return
    gid, uid = _scope(event)

    async def _do():
        async with state.player_lock(gid, uid):
            p = services.do_unequip(state.conn(), state.CFG, gid, uid, item_query)
            await _reply_to(bot, event, p.name, render_status(p, state.CFG))

    await _guard(bot, event, _do())


@cmd_unequip.handle()
async def handle_unequip(bot: Bot, event: Event):
    await _handle_unequip_item(bot, event, _arg(event, "卸下"))


# ---------------------------------------------------------------------------
# 使用
# ---------------------------------------------------------------------------

cmd_use = on_command("使用", rule=to_me(), priority=10, block=True)


async def _handle_use_arg(bot: Bot, event: Event, item_arg: str):
    try:
        requests = parse_multi_item_quantities(item_arg)
    except ValueError as e:
        await _reply(bot, event, str(e))
        return
    if not requests:
        await _reply(bot, event, "用法:使用 物品名")
        return
    gid, uid = _scope(event)

    async def _do():
        async with state.player_lock(gid, uid):
            now = state.now()
            result = services.do_use_many(
                state.conn(), state.CFG, gid, uid, requests, now=now
            )
            lines = ["✅ 使用结算"]
            for entry in result.entries:
                if entry.used > 0:
                    extra = ""
                    if entry.bought > 0:
                        extra = f" (自动购买{entry.bought}个,花费{entry.cost}金币)"
                    line = f"・{entry.name} ×{entry.used}{extra}"
                    if entry.error:
                        line += f"；另有失败:{entry.error}"
                    lines.append(line)
                else:
                    lines.append(f"・{entry.name} 未使用:{entry.error}")
            if result.overdrive_triggered:
                lines.append("💥 你触发了「爆气」负面buff:攻击下降15%,防御下降20%,持续10分钟。")
            lines.append(render_status(result.player, state.CFG))
            await _reply_to(bot, event, result.player.name, "\n".join(lines))

    await _guard(bot, event, _do())


@cmd_use.handle()
async def handle_use(bot: Bot, event: Event):
    await _handle_use_arg(bot, event, _arg(event, "使用"))


# ---------------------------------------------------------------------------
# 回满生命
# ---------------------------------------------------------------------------

cmd_refill_hp = on_command(
    "回满生命",
    aliases={"回满血", "补满生命", "补满血"},
    rule=to_me(),
    priority=10,
    block=True,
)


@cmd_refill_hp.handle()
async def handle_refill_hp(bot: Bot, event: Event):
    gid, uid = _scope(event)

    async def _do():
        async with state.player_lock(gid, uid):
            result = services.do_refill_hp(state.conn(), state.CFG, gid, uid)
            if result.hp_before >= result.hp_max:
                lines = ["生命已满,无需使用药品。"]
            elif result.used_items:
                used = "、".join(f"{item.name}×{item.quantity}" for item in result.used_items)
                lines = [
                    f"✅ 已回复生命:{result.hp_before} → {result.hp_after}/{result.hp_max}",
                    f"使用:{used}",
                ]
                if not result.fully_healed:
                    lines.append("背包回复药已用完,生命尚未回满。")
            else:
                lines = ["背包里没有可回复生命的消耗品。"]
            lines.append(render_status(result.player, state.CFG))
            await _reply_to(bot, event, result.player.name, "\n".join(lines))

    await _guard(bot, event, _do())


# ---------------------------------------------------------------------------
# 回满体力
# ---------------------------------------------------------------------------

cmd_refill_stamina = on_command("回满体力", aliases={"补满体力"}, rule=to_me(), priority=10, block=True)


@cmd_refill_stamina.handle()
async def handle_refill_stamina(bot: Bot, event: Event):
    gid, uid = _scope(event)

    async def _do():
        async with state.player_lock(gid, uid):
            p, cost, overdrive_triggered = services.do_refill_stamina(
                state.conn(), state.CFG, gid, uid, state.now()
            )
            if cost == 0:
                text = "体力已满,无需购买回气丹。\n" + render_status(p, state.CFG)
            else:
                text = f"✅ 已回满体力,消耗{cost}金币。"
                if overdrive_triggered:
                    text += "\n💥 你触发了「爆气」负面buff:攻击下降15%,防御下降20%,持续10分钟。"
                text += "\n" + render_status(p, state.CFG)
            await _reply_to(bot, event, p.name, text)

    await _guard(bot, event, _do())


# ---------------------------------------------------------------------------
# 重铸词条
# ---------------------------------------------------------------------------

cmd_reforge = on_command("重铸", rule=to_me(), priority=10, block=True)


async def _handle_reforge_arg(bot: Bot, event: Event, arg: str):
    parts = arg.split()
    if not parts:
        await _reply(bot, event, "用法:重铸 武器/装备 [次数]")
        return
    slot_query = parts[0]
    try:
        times = int(parts[1]) if len(parts) > 1 else 1
    except ValueError:
        await _reply(bot, event, "次数必须是正整数")
        return
    if times <= 0:
        await _reply(bot, event, "次数必须是正整数")
        return
    gid, uid = _scope(event)

    async def _do():
        async with state.player_lock(gid, uid):
            result = services.do_reforge_equipped(
                state.conn(), state.CFG, gid, uid, slot_query, times, random.Random()
            )
            text = (
                f"🔨 重铸完成:{result.times}次,花费{result.cost}金币\n"
                f"旧词条:{format_affix(result.old_affix) or result.old_affix or '无'}\n"
                f"新词条:{format_affix(result.new_affix) or result.new_affix or '无'}\n"
                + render_status(result.player, state.CFG)
            )
            await _reply_to(bot, event, result.player.name, text)

    await _guard(bot, event, _do())


@cmd_reforge.handle()
async def handle_reforge(bot: Bot, event: Event):
    await _handle_reforge_arg(bot, event, _arg(event, "重铸"))


# ---------------------------------------------------------------------------
# 商店
# ---------------------------------------------------------------------------

cmd_shop = on_command("商店", rule=to_me(), priority=10, block=True)


@cmd_shop.handle()
async def handle_shop(bot: Bot, event: Event):
    await _reply(bot, event, render_shop(state.CFG))


# ---------------------------------------------------------------------------
# 购买 / 买
# ---------------------------------------------------------------------------

cmd_buy = on_command("购买", aliases={"买"}, rule=to_me(), priority=10, block=True)


async def _handle_buy_item(bot: Bot, event: Event, item_query: str):
    if not item_query:
        await _reply(bot, event, "用法:购买 物品名")
        return
    gid, uid = _scope(event)

    async def _do():
        async with state.player_lock(gid, uid):
            p = services.do_buy(state.conn(), state.CFG, gid, uid, item_query)
            await _reply_to(
                bot, event, p.name,
                f"✅ 购买成功!当前金币:{p.gold}\n" + render_inventory(p, state.CFG),
            )

    await _guard(bot, event, _do())


@cmd_buy.handle()
async def handle_buy(bot: Bot, event: Event):
    await _handle_buy_item(bot, event, _arg(event, "购买", "买"))


# ---------------------------------------------------------------------------
# 出售装备
# ---------------------------------------------------------------------------

cmd_sell_gear = on_command(
    "出售装备",
    aliases={"一键出售", "清理装备"},
    rule=to_me(),
    priority=10,
    block=True,
)


@cmd_sell_gear.handle()
async def handle_sell_gear(bot: Bot, event: Event):
    gid, uid = _scope(event)

    async def _do():
        async with state.player_lock(gid, uid):
            result, p = services.do_sell_unequipped_gear(state.conn(), state.CFG, gid, uid)
            await _reply_to(bot, event, p.name, render_sell_result(result, p.gold))

    await _guard(bot, event, _do())


# ---------------------------------------------------------------------------
# 装备养成
# ---------------------------------------------------------------------------

cmd_dismantle_gear = on_command(
    "分解装备",
    aliases={"一键分解装备", "分解武器", "分解防具"},
    rule=to_me(),
    priority=10,
    block=True,
)


def _dismantle_filter_from_text(text: str) -> str:
    if "武器" in text:
        return "weapon"
    if "防具" in text:
        return "armor"
    return "all"


async def _handle_dismantle_gear_arg(bot: Bot, event: Event, slot_filter: str):
    gid, uid = _scope(event)

    async def _do():
        async with state.player_lock(gid, uid):
            result, p = services.do_dismantle_gear(
                state.conn(), state.CFG, gid, uid, slot_filter or "all"
            )
            await _reply_to(bot, event, p.name, render_dismantle_result(result, state.CFG))

    await _guard(bot, event, _do())


@cmd_dismantle_gear.handle()
async def handle_dismantle_gear(bot: Bot, event: Event):
    await _handle_dismantle_gear_arg(
        bot,
        event,
        _dismantle_filter_from_text(event.get_plaintext()),
    )


def _parse_slot_count_arg(arg: str) -> tuple[str, int]:
    parts = str(arg).split()
    if not parts:
        return "", 1
    if len(parts) == 1:
        text = parts[0]
        digits = ""
        while text and text[-1].isdigit():
            digits = text[-1] + digits
            text = text[:-1]
        if digits and text:
            return text, int(digits)
        return parts[0], 1
    return parts[0], int(parts[1])


cmd_enhance_gear = on_command("强化", rule=to_me(), priority=10, block=True)


async def _handle_enhance_gear_arg(bot: Bot, event: Event, arg: str):
    try:
        slot_query, times = _parse_slot_count_arg(arg)
    except ValueError:
        await _reply(bot, event, "次数必须是正整数")
        return
    if times <= 0:
        await _reply(bot, event, "次数必须是正整数")
        return

    gid, uid = _scope(event)

    async def _do():
        async with state.player_lock(gid, uid):
            result = services.do_enhance_equipped(
                state.conn(), state.CFG, gid, uid, slot_query, times, state.now()
            )
            p = repo.get_player(state.conn(), gid, uid)
            await _reply_to(
                bot,
                event,
                p.name,
                render_enhance_result(result, state.CFG) + "\n" + render_status(p, state.CFG),
            )

    await _guard(bot, event, _do())


@cmd_enhance_gear.handle()
async def handle_enhance_gear(bot: Bot, event: Event):
    await _handle_enhance_gear_arg(bot, event, _arg(event, "强化"))


cmd_star_up_gear = on_command("升星", rule=to_me(), priority=10, block=True)


async def _handle_star_up_gear_arg(bot: Bot, event: Event, arg: str):
    gid, uid = _scope(event)

    async def _do():
        async with state.player_lock(gid, uid):
            result = services.do_star_up_equipped(
                state.conn(), state.CFG, gid, uid, arg, state.now()
            )
            p = repo.get_player(state.conn(), gid, uid)
            await _reply_to(
                bot,
                event,
                p.name,
                render_star_up_result(result, state.CFG) + "\n" + render_status(p, state.CFG),
            )

    await _guard(bot, event, _do())


@cmd_star_up_gear.handle()
async def handle_star_up_gear(bot: Bot, event: Event):
    await _handle_star_up_gear_arg(bot, event, _arg(event, "升星"))


# ---------------------------------------------------------------------------
# 世界Boss
# ---------------------------------------------------------------------------

cmd_void_sacrifice = on_command(
    "虚空献祭",
    aliases={"献祭", "十连献祭", "献祭十连"},
    rule=to_me(),
    priority=10,
    block=True,
)


async def _handle_void_sacrifice_arg(bot: Bot, event: Event, arg: str):
    text = str(arg or "").strip()
    if event.get_plaintext().strip() in {"十连献祭", "/十连献祭", "献祭十连", "/献祭十连"}:
        text = "10"
    try:
        draw_count = parse_draw_count(text)
    except ValueError as e:
        await _reply(bot, event, str(e))
        return
    gid, uid = _scope(event)

    async def _do():
        async with state.player_lock(gid, uid):
            result = services.do_void_sacrifice(
                state.conn(), state.CFG, gid, uid, draw_count, state.now(), random.Random()
            )
            await _reply_to(
                bot,
                event,
                result.player.name,
                render_void_sacrifice(result, state.CFG),
            )

    await _guard(bot, event, _do())


@cmd_void_sacrifice.handle()
async def handle_void_sacrifice(bot: Bot, event: Event):
    await _handle_void_sacrifice_arg(
        bot,
        event,
        _arg(event, "虚空献祭", "献祭", "十连献祭", "献祭十连"),
    )


cmd_world_boss = on_command(
    "世界boss",
    aliases={"世界boss状态"},
    rule=to_me(),
    priority=10,
    block=True,
)


async def _handle_world_boss_status(bot: Bot, event: Event):
    gid, _ = _scope(event)

    async def _do():
        result = services.do_world_boss_status(state.conn(), state.CFG, gid, state.now())
        await _reply(bot, event, render_world_boss_status(result, state.CFG))

    await _guard(bot, event, _do())


@cmd_world_boss.handle()
async def handle_world_boss(bot: Bot, event: Event):
    await _handle_world_boss_status(bot, event)


cmd_attack_world_boss = on_command(
    "进攻世界boss",
    aliases={"攻击世界boss", "挑战世界boss"},
    rule=to_me(),
    priority=10,
    block=True,
)


async def _handle_attack_world_boss(bot: Bot, event: Event):
    gid, uid = _scope(event)

    async def _do():
        async with state.player_lock(gid, uid):
            result = services.do_attack_world_boss(
                state.conn(), state.CFG, gid, uid, state.now(), random.Random()
            )
            await _reply_to(
                bot,
                event,
                result.player.name,
                render_world_boss_attack(result, state.CFG),
            )

    await _guard(bot, event, _do())


@cmd_attack_world_boss.handle()
async def handle_attack_world_boss(bot: Bot, event: Event):
    await _handle_attack_world_boss(bot, event)


cmd_world_boss_ranking = on_command(
    "世界boss排行",
    rule=to_me(),
    priority=10,
    block=True,
)


@cmd_world_boss_ranking.handle()
async def handle_world_boss_ranking(bot: Bot, event: Event):
    await _handle_world_boss_status(bot, event)


# ---------------------------------------------------------------------------
# 前往 / 回层
# ---------------------------------------------------------------------------

cmd_travel = on_command("前往", aliases={"回层", "去"}, rule=to_me(), priority=10, block=True)


async def _handle_travel_arg(bot: Bot, event: Event, depth_query: str):
    if not depth_query:
        await _reply(bot, event, "用法: 前往 层数，例如「前往 35」或「前往 最深」")
        return
    gid, uid = _scope(event)

    async def _do():
        async with state.player_lock(gid, uid):
            p = services.do_travel_depth(state.conn(), state.CFG, gid, uid, depth_query)
            await _reply_to(bot, event, p.name, f"已前往第 {p.current_depth} 层。\n" + render_status(p, state.CFG))

    await _guard(bot, event, _do())


@cmd_travel.handle()
async def handle_travel(bot: Bot, event: Event):
    await _handle_travel_arg(bot, event, _arg(event, "前往", "回层", "去"))


# ---------------------------------------------------------------------------
# 回到并探索
# ---------------------------------------------------------------------------

cmd_travel_explore = on_command("回到", rule=to_me(), priority=10, block=True)


async def _handle_travel_explore_arg(bot: Bot, event: Event, arg: str):
    try:
        depth_query = parse_travel_explore_arg(arg)
    except ValueError as e:
        await _reply(bot, event, str(e))
        return
    gid, uid = _scope(event)

    async def _do():
        async with state.player_lock(gid, uid):
            p, res = services.do_travel_and_explore(
                state.conn(), state.CFG, gid, uid, depth_query, state.now(), random.Random()
            )
            await _reply_to(bot, event, p.name, render_explore(p, res, state.CFG))

    await _guard(bot, event, _do())


@cmd_travel_explore.handle()
async def handle_travel_explore(bot: Bot, event: Event):
    await _handle_travel_explore_arg(bot, event, _arg(event, "回到"))


# ---------------------------------------------------------------------------
# 排行榜 / 排名
# ---------------------------------------------------------------------------

cmd_ranking = on_command("排行榜", aliases={"排名"}, rule=to_me(), priority=10, block=True)


async def _handle_ranking_arg(bot: Bot, event: Event, arg: str):
    key = "depth" if arg in ("深度", "depth") else "level"
    gid, uid = _scope(event)

    async def _do():
        async with state.player_lock(gid, uid):
            players = services.get_ranking(state.conn(), state.CFG, gid, key=key)
            await _reply(bot, event, render_ranking(players, state.CFG, key))

    await _guard(bot, event, _do())


@cmd_ranking.handle()
async def handle_ranking(bot: Bot, event: Event):
    await _handle_ranking_arg(bot, event, _arg(event, "排行榜", "排名"))


# ---------------------------------------------------------------------------
# 帮助 / 菜单 / ?
# ---------------------------------------------------------------------------

_HELP_TEXT = """🎮 挂机RPG 指令菜单
──────────────
注册 <名字>   — 创建角色
探索         — 下潜冒险(消耗体力)
状态         — 查看角色面板
背包         — 查看物品
装备 <物品>   — 装备武器/护甲
购买装备 <物品> — 购买武器/护甲并立即装备
卸下 <物品>   — 卸下装备
使用 <物品>   — 使用消耗品(药水/丹药/符箓)
使用 <物品> <数量> — 批量使用消耗品
使用 <物品A> <物品B> — 多物品使用,缺少时自动购买
商店         — 查看商店
购买 <物品>   — 购买物品
出售装备      — 一键出售未装备武器/防具
虚空献祭 [1/10] — 花金币献祭抽取装备
世界boss      — 查看世界Boss状态
进攻世界boss   — 消耗50体力进攻世界Boss
回满生命      — 使用背包药品补满生命
回满体力      — 花金币购买回气丹并补满体力
重铸 武器/装备 [次数] — 花金币重随机词条
前往 <层数>   — 回到已探索过的层数刷资源
回到 <层数> 并探索 — 回层后立刻探索
排行榜       — 等级榜
排行榜 深度   — 深度榜
──────────────
⚔️ 剑(均衡) 刀(高攻) 枪(加血) 暗器(极限攻)
🛡️ 轻甲(高血) 重甲(高防)
✨ 攻击/防御临时Buff 按步数消耗
💊 体力药水可买 加速循环
凡→良→上→极→仙 五品 最深100层
──────────────
私聊直接发指令;群里/频道里需 @机器人。"""

cmd_help = on_command("帮助", aliases={"菜单", "?"}, rule=to_me(), priority=10, block=True)


@cmd_help.handle()
async def handle_help(bot: Bot, event: Event):
    await _reply(bot, event, _HELP_TEXT)


# ---------------------------------------------------------------------------
# 模糊指令兜底
# ---------------------------------------------------------------------------

cmd_fuzzy = on_message(rule=to_me(), priority=90, block=False)


@cmd_fuzzy.handle()
async def handle_fuzzy(bot: Bot, event: Event):
    parsed = parse_fuzzy_command(event.get_plaintext())
    if parsed is None:
        return

    if parsed.command == "register":
        await _handle_register_name(bot, event, parsed.arg)
    elif parsed.command == "explore":
        await handle_explore(bot, event)
    elif parsed.command == "status":
        await handle_status(bot, event)
    elif parsed.command == "inventory":
        await handle_inventory(bot, event)
    elif parsed.command == "equip":
        await _handle_equip_item(bot, event, parsed.arg)
    elif parsed.command == "buy_equip":
        await _handle_buy_equip_item(bot, event, parsed.arg)
    elif parsed.command == "unequip":
        await _handle_unequip_item(bot, event, parsed.arg)
    elif parsed.command == "use":
        await _handle_use_arg(bot, event, parsed.arg)
    elif parsed.command == "refill_hp":
        await handle_refill_hp(bot, event)
    elif parsed.command == "refill_stamina":
        await handle_refill_stamina(bot, event)
    elif parsed.command == "reforge":
        await _handle_reforge_arg(bot, event, parsed.arg)
    elif parsed.command == "shop":
        await handle_shop(bot, event)
    elif parsed.command == "buy":
        await _handle_buy_item(bot, event, parsed.arg)
    elif parsed.command == "sell_gear":
        await handle_sell_gear(bot, event)
    elif parsed.command == "dismantle_gear":
        await _handle_dismantle_gear_arg(bot, event, parsed.arg or "all")
    elif parsed.command == "enhance_gear":
        await _handle_enhance_gear_arg(bot, event, parsed.arg)
    elif parsed.command == "star_up_gear":
        await _handle_star_up_gear_arg(bot, event, parsed.arg)
    elif parsed.command == "void_sacrifice":
        await _handle_void_sacrifice_arg(bot, event, parsed.arg)
    elif parsed.command == "world_boss_status":
        await _handle_world_boss_status(bot, event)
    elif parsed.command == "world_boss_attack":
        await _handle_attack_world_boss(bot, event)
    elif parsed.command == "world_boss_ranking":
        await _handle_world_boss_status(bot, event)
    elif parsed.command == "travel":
        await _handle_travel_arg(bot, event, parsed.arg)
    elif parsed.command == "travel_explore":
        await _handle_travel_explore_arg(bot, event, parsed.arg)
    elif parsed.command == "ranking":
        await _handle_ranking_arg(bot, event, parsed.arg)
    elif parsed.command == "help":
        await handle_help(bot, event)
    else:
        return

    await cmd_fuzzy.finish()


# ---------------------------------------------------------------------------
# 未知指令兜底
# ---------------------------------------------------------------------------

_UNKNOWN_COMMAND_REPLIES = UNKNOWN_COMMAND_REPLIES

cmd_unknown = on_message(rule=to_me(), priority=99, block=True)


@cmd_unknown.handle()
async def handle_unknown(bot: Bot, event: Event):
    text = event.get_plaintext().strip()
    if not text:
        return
    await _reply(bot, event, random.choice(_UNKNOWN_COMMAND_REPLIES))


async def _world_boss_announcement_loop():
    while True:
        await asyncio.sleep(60)
        bots = nonebot.get_bots()
        if not bots:
            continue
        bot = next(iter(bots.values()))
        now = state.now()
        for result in services.get_due_world_boss_announcements(
            state.conn(), state.CFG, now
        ):
            group_id = result.boss["group_id"]
            if not str(group_id).isdigit():
                continue
            try:
                await bot.call_api(
                    "send_group_msg",
                    group_id=int(group_id),
                    message=render_world_boss_status(result, state.CFG),
                )
                services.mark_world_boss_announced(
                    state.conn(), result.boss["id"], state.now()
                )
            except Exception:
                logger.exception("世界Boss定时公告发送失败")


@nonebot.get_driver().on_startup
async def _start_world_boss_announcement_loop():
    global _world_boss_announcement_task
    if _world_boss_announcement_task is None or _world_boss_announcement_task.done():
        _world_boss_announcement_task = asyncio.create_task(
            _world_boss_announcement_loop()
        )
