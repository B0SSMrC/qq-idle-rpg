from __future__ import annotations
import random
from game_core.models import Player, ExploreResult, GameConfig, SellResult
from game_core.stats import hp_max, attack, defense, power

COMBAT_WIN_TEMPLATES = [
    "第{depth}层 ⚔️ {monster} → {rounds}回合击败  +{exp}exp +{gold}金币{extra}",
    "第{depth}层 ⚔️ 遭遇{monster}，{rounds}回合后取胜  +{exp}exp +{gold}金币{extra}",
    "第{depth}层 ⚔️ {monster}拦路，被你用{rounds}回合解决  +{exp}exp +{gold}金币{extra}",
    "第{depth}层 ⚔️ 与{monster}短兵相接，{rounds}回合胜出  +{exp}exp +{gold}金币{extra}",
    "第{depth}层 ⚔️ 斩退{monster}，战斗持续{rounds}回合  +{exp}exp +{gold}金币{extra}",
]


def _item_name(cfg: GameConfig, item_id: str) -> str:
    it = cfg.items.get(item_id)
    return it.name if it else item_id


def render_explore(player: Player, res: ExploreResult, cfg: GameConfig) -> str:
    lines = [f"🗡️ 【{player.name}】的下潜 (第{res.depth_before}层 → 第{res.depth_after}层)", ""]
    for s in res.steps:
        if s.kind == "combat" and s.won:
            extra = f"  ✨ 掉落【{'、'.join(_item_name(cfg, i) for i in s.items)}】" if s.items else ""
            lines.append(random.choice(COMBAT_WIN_TEMPLATES).format(
                depth=s.depth,
                monster=s.monster,
                rounds=s.rounds,
                exp=s.exp,
                gold=s.gold,
                extra=extra,
            ))
        elif s.kind == "combat" and not s.won:
            lines.append(f"第{s.depth}层 ⚔️ 不敌{s.monster},重伤回城…")
        elif s.kind == "treasure":
            lines.append(f"第{s.depth}层 📦 发现宝箱  +{s.gold}金币")
        elif s.kind == "trap":
            lines.append(f"第{s.depth}层 ⚠️ {s.text or '踩中陷阱'}")
        else:  # flavor
            lines.append(f"第{s.depth}层 🚶 {s.text}")
    lines.append("──────────────")
    got = f"  获得{len(res.items_gained)}件物品" if res.items_gained else ""
    lines.append(f"本次合计:+{res.total_exp}exp  +{res.total_gold}金币{got}")
    lines.append(f"❤️ HP {res.hp_after}/{res.hp_max}   ⚡ 体力 {res.stamina_left}")
    if res.level_ups > 0:
        lines.append(f"📊 升级 +{res.level_ups}!  当前 Lv.{player.level}")
    lines.append(f"🏆 最深抵达 第{player.max_depth}层")
    if res.defeated:
        lines.append("💀 重伤休整,当前层数保留(金币略有损失)")
    elif res.stamina_left < cfg.balance.stamina_cost_per_step:
        lines.append("💤 体力耗尽,攒一攒再来下潜~")
    return "\n".join(lines)


def render_status(player: Player, cfg: GameConfig) -> str:
    lines = [
        f"🛡️ {player.name}  Lv.{player.level}  (当前世界)",
        f"经验 {player.exp}",
        f"❤️ HP {player.current_hp}/{hp_max(player, cfg)}   ⚡ 体力 {player.stamina}/{cfg.balance.stamina_max}",
        f"⚔️ 攻击 {attack(player, cfg)}   🛡️ 防御 {defense(player, cfg)}   💪 战力 {power(player, cfg)}",
        f"💰 金币 {player.gold}   🏆 最深 第{player.max_depth}层",
        "🎒 装备:" + ("、".join(_item_name(cfg, i.item_id) for i in player.inventory if i.equipped) or "无"),
    ]
    if player.buffs:
        lines.append("✨ Buff:")
        for b in player.buffs:
            icon = "⚔️攻击" if b.type == "atk" else "🛡️防御"
            lines.append(f"  {icon}+{b.amount}  (剩余{b.steps_left}步)")
    if player.overdrive_until > player.last_active_at:
        remaining = max(1, (player.overdrive_until - player.last_active_at + 59) // 60)
        lines.append(f"💥 爆气:攻击-15% 防御-20% (剩余约{remaining}分钟)")
    return "\n".join(lines)


def render_sell_result(result: SellResult, gold_after: int) -> str:
    lines = ["💰 一键出售结算"]
    if not result.sold_items:
        lines.append("没有可出售的未装备武器/防具。")
    else:
        count = sum(item.quantity for item in result.sold_items)
        lines.append(f"售出 {count} 件装备，获得 {result.total_gold} 金币")
        lines.append("──────────────")
        for item in result.sold_items:
            lines.append(
                f"· {item.name} x{item.quantity}  "
                f"{item.unit_price}/件 = {item.total_price}"
            )
    lines.append(f"当前金币: {gold_after}")
    return "\n".join(lines)


def render_ranking(players, cfg: GameConfig, key: str = "level") -> str:
    title = "🏆 当前世界等级榜" if key == "level" else "🏆 当前世界深度榜"
    lines = [title]
    medals = ["🥇", "🥈", "🥉"]
    for i, p in enumerate(players):
        rank = medals[i] if i < 3 else f"{i + 1}."
        lines.append(f"{rank} {p.name}  Lv.{p.level}  最深第{p.max_depth}层")
    if len(lines) == 1:
        lines.append("还没有人上榜,快发「探索」吧~")
    return "\n".join(lines)


def _shop_category(it) -> str:
    if it.slot == "weapon":
        return "⚔️ 武器"
    if it.slot == "armor":
        return "🛡️ 护甲"
    if it.heal > 0:
        return "💊 治疗"
    if it.buff_type in ("atk", "def"):
        return "✨ 临时增益"
    if it.buff_type == "stamina":
        return "⚡ 体力"
    return "📦 其他"


def _shop_stats(it) -> str:
    parts = []
    if it.atk:
        parts.append(f"⚔️{it.atk:+d}")
    if it.defense:
        parts.append(f"🛡️{it.defense:+d}")
    if it.hp:
        parts.append(f"❤️{it.hp:+d}")
    if it.heal:
        parts.append(f"💊回{it.heal}")
    if it.buff_type == "atk":
        parts.append(f"✨攻击+{it.buff_value}/{it.buff_steps}步")
    elif it.buff_type == "def":
        parts.append(f"✨防御+{it.buff_value}/{it.buff_steps}步")
    elif it.buff_type == "stamina":
        parts.append(f"⚡体力+{it.buff_value}")
    return " ".join(parts)


def render_shop(cfg: GameConfig) -> str:
    from game_core.shop import list_shop
    groups = {
        "⚔️ 武器": [],
        "🛡️ 护甲": [],
        "💊 治疗": [],
        "✨ 临时增益": [],
        "⚡ 体力": [],
        "📦 其他": [],
    }
    for it in list_shop(cfg):
        groups[_shop_category(it)].append(it)

    lines = [
        "🏪 云游商店",
        "发「购买 物品名」即可购买",
    ]
    for title, items in groups.items():
        if not items:
            continue
        lines.append("──────────────")
        lines.append(title)
        for it in items:
            stats = _shop_stats(it)
            detail = f"  {stats}" if stats else ""
            lines.append(f"・{it.name}  💰{it.price}金币{detail}")
    return "\n".join(lines)


def render_inventory(player: Player, cfg: GameConfig) -> str:
    if not player.inventory:
        return "🎒 背包空空如也,发「探索」去找点东西吧~"
    lines = ["🎒 背包"]
    for it in player.inventory:
        tag = "(已装备)" if it.equipped else ""
        lines.append(f"・{_item_name(cfg, it.item_id)} ×{it.quantity}{tag}")
    return "\n".join(lines)
