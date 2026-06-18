"""RPG 命令插件 — 兼容 nonebot-adapter-qq 的单聊/群/频道三种消息事件。

已验证的适配器 API (nonebot-adapter-qq 1.7.1):
  事件类:
    C2CMessageCreateEvent      单聊(私信)   user = author.user_openid
    GroupAtMessageCreateEvent  群 @消息       user = author.member_openid,group = group_openid
    AtMessageCreateEvent       频道 @消息     user = author.id,            guild = guild_id
  三者都有 event.get_user_id() 与 event.to_me;回复统一 await bot.send(event, text)。

「世界/排行榜范围」(对应存档的 group_id):
  群   → group_openid
  单聊 → 常量 "c2c"(同一私聊世界,所有私聊玩家同榜)
  频道 → "guild_{guild_id}"(同一频道服务器同榜)
"""
from __future__ import annotations

import random

import nonebot
from nonebot import on_command
from nonebot.rule import to_me
from nonebot.adapters import Bot, Event

from nonebot.adapters.qq import (
    GroupAtMessageCreateEvent,
    C2CMessageCreateEvent,
    AtMessageCreateEvent,
)

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
# 范围解析 / 通用工具
# ---------------------------------------------------------------------------


def _scope(event: Event) -> tuple[str, str]:
    """返回 (group_id, user_id):group_id 是排行榜/世界范围,因事件类型而异。"""
    uid = event.get_user_id()
    if isinstance(event, GroupAtMessageCreateEvent):
        return event.group_openid, uid
    if isinstance(event, AtMessageCreateEvent):
        return f"guild_{event.guild_id}", uid
    if isinstance(event, C2CMessageCreateEvent):
        return "c2c", uid
    return "unknown", uid


def _arg(event: Event, *cmd_words: str) -> str:
    """从消息纯文本里剥掉指令词,返回参数部分。"""
    text = event.get_plaintext().strip()
    for w in cmd_words:
        text = text.removeprefix(w)
    return text.strip()


async def _reply(bot: Bot, event: Event, text: str):
    return await bot.send(event, text)


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


@cmd_register.handle()
async def handle_register(bot: Bot, event: Event):
    name = _arg(event, "注册", "创建")
    if not name:
        await _reply(bot, event, "用法:注册 角色名(群里/频道里需 @机器人)")
        return
    gid, uid = _scope(event)

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
async def handle_explore(bot: Bot, event: Event):
    gid, uid = _scope(event)

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
async def handle_status(bot: Bot, event: Event):
    gid, uid = _scope(event)

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
async def handle_inventory(bot: Bot, event: Event):
    gid, uid = _scope(event)

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
async def handle_equip(bot: Bot, event: Event):
    item_query = _arg(event, "装备")
    if not item_query:
        await _reply(bot, event, "用法:装备 物品名")
        return
    gid, uid = _scope(event)

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
async def handle_unequip(bot: Bot, event: Event):
    item_query = _arg(event, "卸下")
    if not item_query:
        await _reply(bot, event, "用法:卸下 物品名")
        return
    gid, uid = _scope(event)

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
async def handle_use(bot: Bot, event: Event):
    item_query = _arg(event, "使用")
    if not item_query:
        await _reply(bot, event, "用法:使用 物品名")
        return
    gid, uid = _scope(event)

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
async def handle_shop(bot: Bot, event: Event):
    await _reply(bot, event, render_shop(state.CFG))


# ---------------------------------------------------------------------------
# 购买 / 买
# ---------------------------------------------------------------------------

cmd_buy = on_command("购买", aliases={"买"}, rule=to_me(), priority=10, block=True)


@cmd_buy.handle()
async def handle_buy(bot: Bot, event: Event):
    item_query = _arg(event, "购买", "买")
    if not item_query:
        await _reply(bot, event, "用法:购买 物品名")
        return
    gid, uid = _scope(event)

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
async def handle_ranking(bot: Bot, event: Event):
    arg = _arg(event, "排行榜", "排名")
    key = "depth" if arg in ("深度", "depth") else "level"
    gid, uid = _scope(event)

    async def _do():
        async with state.player_lock(gid, uid):
            players = services.get_ranking(state.conn(), state.CFG, gid, key=key)
            await _reply(bot, event, render_ranking(players, state.CFG, key))

    await _guard(bot, event, _do())


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
卸下 <物品>   — 卸下装备
使用 <物品>   — 使用消耗品(药水/丹药/符箓)
商店         — 查看商店
购买 <物品>   — 购买物品
排行榜       — 等级榜
排行榜 深度   — 深度榜
──────────────
⚔️ 剑(均衡) 刀(高攻) 枪(加血) 暗器(极限攻)
🛡️ 轻甲(高血) 重甲(高防)
✨ 攻击/防御临时Buff 按步数消耗
💊 体力药水可买 加速循环
凡→良→上→极→仙 五品 最深50层
──────────────
私聊直接发指令;群里/频道里需 @机器人。"""

cmd_help = on_command("帮助", aliases={"菜单", "?"}, rule=to_me(), priority=10, block=True)


@cmd_help.handle()
async def handle_help(bot: Bot, event: Event):
    await _reply(bot, event, _HELP_TEXT)
