"""RPG 命令插件 — 对接 nonebot-adapter-qq GroupAtMessageCreateEvent。

已验证的适配器 API (nonebot-adapter-qq 1.7.1):
  事件类:  GroupAtMessageCreateEvent  (继承 GroupMessageCreateEvent)
  Group id: event.group_openid        (str)
  User id:  event.author.member_openid (str, author: GroupMemberAuthor)
  回复:     await bot.send(event, text)
            → Bot.send() 路由到 send_to_group(group_openid=event.group_openid, ...)
"""
from __future__ import annotations

import random
from typing import Any

import nonebot
from nonebot import on_command
from nonebot.rule import to_me
from nonebot.adapters import Bot, Event

from nonebot.adapters.qq import GroupAtMessageCreateEvent

import bot.state as state
from app import services
from bot.formatting import (
    render_explore,
    render_status,
    render_ranking,
    render_shop,
    render_inventory,
)
from game_core.errors import GameError
from storage import repository as repo

logger = nonebot.log.logger

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _ids(event: GroupAtMessageCreateEvent) -> tuple[str, str]:
    """Return (group_id, user_id) from a group at-message event."""
    return event.group_openid, event.author.member_openid


async def _reply(bot: Bot, event: Event, text: str) -> Any:
    return await bot.send(event, text)


async def _guard(bot: Bot, event: GroupAtMessageCreateEvent, coro):
    """Await *coro* with shared GameError / Exception guard."""
    try:
        await coro
    except GameError as e:
        await _reply(bot, event, str(e))
    except Exception:
        logger.exception("未处理的异常")
        await _reply(bot, event, "⚠️ 出了点小问题,已记录,稍后再试~")


# ---------------------------------------------------------------------------
# 注册 / 创建
# ---------------------------------------------------------------------------

cmd_register = on_command("注册", aliases={"创建"}, rule=to_me(), priority=10, block=True)


@cmd_register.handle()
async def handle_register(bot: Bot, event: GroupAtMessageCreateEvent):
    raw = str(event.get_message()).strip()
    name = raw.removeprefix("注册").removeprefix("创建").strip()
    if not name:
        await _reply(bot, event, "用法:@bot 注册 角色名")
        return
    gid, uid = _ids(event)

    async def _do():
        async with state.player_lock(gid, uid):
            p = services.register(state.conn(), state.CFG, gid, uid, name, state.now())
            await _reply(bot, event, f"✅ 角色「{p.name}」已创建!发「探索」开始冒险吧~")

    await _guard(bot, event, _do())


# ---------------------------------------------------------------------------
# 探索 / 下潜 / 冒险
# ---------------------------------------------------------------------------

cmd_explore = on_command("探索", aliases={"下潜", "冒险"}, rule=to_me(), priority=10, block=True)


@cmd_explore.handle()
async def handle_explore(bot: Bot, event: GroupAtMessageCreateEvent):
    gid, uid = _ids(event)

    async def _do():
        async with state.player_lock(gid, uid):
            res = services.do_explore(
                state.conn(), state.CFG, gid, uid, state.now(), random.Random()
            )
            p = repo.get_player(state.conn(), gid, uid)
            await _reply(bot, event, render_explore(p, res, state.CFG))

    await _guard(bot, event, _do())


# ---------------------------------------------------------------------------
# 状态 / 我 / 角色
# ---------------------------------------------------------------------------

cmd_status = on_command("状态", aliases={"我", "角色"}, rule=to_me(), priority=10, block=True)


@cmd_status.handle()
async def handle_status(bot: Bot, event: GroupAtMessageCreateEvent):
    gid, uid = _ids(event)

    async def _do():
        async with state.player_lock(gid, uid):
            p = services.status(state.conn(), state.CFG, gid, uid, state.now())
            await _reply(bot, event, render_status(p, state.CFG))

    await _guard(bot, event, _do())


# ---------------------------------------------------------------------------
# 背包 / 物品
# ---------------------------------------------------------------------------

cmd_inventory = on_command("背包", aliases={"物品"}, rule=to_me(), priority=10, block=True)


@cmd_inventory.handle()
async def handle_inventory(bot: Bot, event: GroupAtMessageCreateEvent):
    gid, uid = _ids(event)

    async def _do():
        async with state.player_lock(gid, uid):
            p = repo.get_player(state.conn(), gid, uid)
            if p is None:
                await _reply(bot, event, "你还没有角色,先发「注册 角色名」吧~")
                return
            await _reply(bot, event, render_inventory(p, state.CFG))

    await _guard(bot, event, _do())


# ---------------------------------------------------------------------------
# 装备
# ---------------------------------------------------------------------------

cmd_equip = on_command("装备", rule=to_me(), priority=10, block=True)


@cmd_equip.handle()
async def handle_equip(bot: Bot, event: GroupAtMessageCreateEvent):
    raw = str(event.get_message()).strip()
    item_query = raw.removeprefix("装备").strip()
    if not item_query:
        await _reply(bot, event, "用法:@bot 装备 物品名")
        return
    gid, uid = _ids(event)

    async def _do():
        async with state.player_lock(gid, uid):
            p = services.do_equip(state.conn(), state.CFG, gid, uid, item_query)
            await _reply(bot, event, render_status(p, state.CFG))

    await _guard(bot, event, _do())


# ---------------------------------------------------------------------------
# 卸下
# ---------------------------------------------------------------------------

cmd_unequip = on_command("卸下", rule=to_me(), priority=10, block=True)


@cmd_unequip.handle()
async def handle_unequip(bot: Bot, event: GroupAtMessageCreateEvent):
    raw = str(event.get_message()).strip()
    item_query = raw.removeprefix("卸下").strip()
    if not item_query:
        await _reply(bot, event, "用法:@bot 卸下 物品名")
        return
    gid, uid = _ids(event)

    async def _do():
        async with state.player_lock(gid, uid):
            p = services.do_unequip(state.conn(), state.CFG, gid, uid, item_query)
            await _reply(bot, event, render_status(p, state.CFG))

    await _guard(bot, event, _do())


# ---------------------------------------------------------------------------
# 使用
# ---------------------------------------------------------------------------

cmd_use = on_command("使用", rule=to_me(), priority=10, block=True)


@cmd_use.handle()
async def handle_use(bot: Bot, event: GroupAtMessageCreateEvent):
    raw = str(event.get_message()).strip()
    item_query = raw.removeprefix("使用").strip()
    if not item_query:
        await _reply(bot, event, "用法:@bot 使用 物品名")
        return
    gid, uid = _ids(event)

    async def _do():
        async with state.player_lock(gid, uid):
            p = services.do_use(state.conn(), state.CFG, gid, uid, item_query)
            await _reply(bot, event, render_status(p, state.CFG))

    await _guard(bot, event, _do())


# ---------------------------------------------------------------------------
# 商店
# ---------------------------------------------------------------------------

cmd_shop = on_command("商店", rule=to_me(), priority=10, block=True)


@cmd_shop.handle()
async def handle_shop(bot: Bot, event: GroupAtMessageCreateEvent):
    await _reply(bot, event, render_shop(state.CFG))


# ---------------------------------------------------------------------------
# 购买 / 买
# ---------------------------------------------------------------------------

cmd_buy = on_command("购买", aliases={"买"}, rule=to_me(), priority=10, block=True)


@cmd_buy.handle()
async def handle_buy(bot: Bot, event: GroupAtMessageCreateEvent):
    raw = str(event.get_message()).strip()
    item_query = raw.removeprefix("购买").removeprefix("买").strip()
    if not item_query:
        await _reply(bot, event, "用法:@bot 购买 物品名")
        return
    gid, uid = _ids(event)

    async def _do():
        async with state.player_lock(gid, uid):
            p = services.do_buy(state.conn(), state.CFG, gid, uid, item_query)
            await _reply(
                bot, event,
                f"✅ 购买成功!当前金币:{p.gold}\n" + render_inventory(p, state.CFG),
            )

    await _guard(bot, event, _do())


# ---------------------------------------------------------------------------
# 排行榜 / 排名
# ---------------------------------------------------------------------------

cmd_ranking = on_command("排行榜", aliases={"排名"}, rule=to_me(), priority=10, block=True)


@cmd_ranking.handle()
async def handle_ranking(bot: Bot, event: GroupAtMessageCreateEvent):
    raw = str(event.get_message()).strip()
    arg = raw.removeprefix("排行榜").removeprefix("排名").strip()
    key = "depth" if arg in ("深度", "depth") else "level"
    gid, uid = _ids(event)

    async def _do():
        async with state.player_lock(gid, uid):
            players = services.get_ranking(state.conn(), state.CFG, gid, key=key)
            await _reply(bot, event, render_ranking(players, state.CFG, key))

    await _guard(bot, event, _do())


# ---------------------------------------------------------------------------
# 帮助 / 菜单 / ?
# ---------------------------------------------------------------------------

_HELP_TEXT = """🎮 挂机RPG 指令菜单(@bot + 指令)
──────────────
注册 <名字>   — 创建角色
探索         — 下潜冒险(消耗体力)
状态         — 查看角色面板
背包         — 查看物品
装备 <物品>   — 装备物品
卸下 <物品>   — 卸下装备
使用 <物品>   — 使用消耗品
商店         — 查看商店
购买 <物品>   — 购买物品
排行榜       — 等级榜
排行榜 深度   — 深度榜
──────────────
体力满时发「探索」,获得装备后「装备」,血量低时「购买 治疗药水」"""

cmd_help = on_command("帮助", aliases={"菜单", "?"}, rule=to_me(), priority=10, block=True)


@cmd_help.handle()
async def handle_help(bot: Bot, event: GroupAtMessageCreateEvent):
    await _reply(bot, event, _HELP_TEXT)
