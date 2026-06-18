from __future__ import annotations
from game_core.models import Player, ExploreResult, GameConfig
from game_core.stats import hp_max, attack, defense, power


def _item_name(cfg: GameConfig, item_id: str) -> str:
    it = cfg.items.get(item_id)
    return it.name if it else item_id


def render_explore(player: Player, res: ExploreResult, cfg: GameConfig) -> str:
    lines = [f"🗡️ 【{player.name}】的下潜 (第{res.depth_before}层 → 第{res.depth_after}层)", ""]
    for s in res.steps:
        if s.kind == "combat" and s.won:
            extra = f"  ✨ 掉落【{'、'.join(_item_name(cfg, i) for i in s.items)}】" if s.items else ""
            lines.append(f"第{s.depth}层 ⚔️ {s.monster} → {s.rounds}回合击败  +{s.exp}exp +{s.gold}金币{extra}")
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
        lines.append("💀 重伤回城,已回到第 1 层(金币略有损失)")
    elif res.stamina_left < cfg.balance.stamina_cost_per_step:
        lines.append("💤 体力耗尽,攒一攒再来下潜~")
    return "\n".join(lines)


def render_status(player: Player, cfg: GameConfig) -> str:
    lines = [
        f"🛡️ {player.name}  Lv.{player.level}  (本群)",
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
    return "\n".join(lines)
    return "\n".join(lines)


def render_ranking(players, cfg: GameConfig, key: str = "level") -> str:
    title = "🏆 本群等级榜" if key == "level" else "🏆 本群深度榜"
    lines = [title]
    medals = ["🥇", "🥈", "🥉"]
    for i, p in enumerate(players):
        rank = medals[i] if i < 3 else f"{i + 1}."
        lines.append(f"{rank} {p.name}  Lv.{p.level}  最深第{p.max_depth}层")
    if len(lines) == 1:
        lines.append("还没有人上榜,快发「探索」吧~")
    return "\n".join(lines)


def render_shop(cfg: GameConfig) -> str:
    from game_core.shop import list_shop
    lines = ["🏪 商店(发「购买 物品名」)"]
    for it in list_shop(cfg):
        lines.append(f"・{it.name}  {it.price}金币")
    return "\n".join(lines)


def render_inventory(player: Player, cfg: GameConfig) -> str:
    if not player.inventory:
        return "🎒 背包空空如也,发「探索」去找点东西吧~"
    lines = ["🎒 背包"]
    for it in player.inventory:
        tag = "(已装备)" if it.equipped else ""
        lines.append(f"・{_item_name(cfg, it.item_id)} ×{it.quantity}{tag}")
    return "\n".join(lines)
