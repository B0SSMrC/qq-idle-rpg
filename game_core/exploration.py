from __future__ import annotations
import random
from game_core.models import Player, GameConfig, StepLog, ExploreResult
from game_core import stats, stamina as stamina_mod, combat, progression, loot


def _pick_event(cfg: GameConfig, depth: int, rng: random.Random):
    if depth >= 80:
        combat_events = [
            e for e in cfg.events
            if e.type == "combat" and e.depth_min <= depth <= e.depth_max
        ]
        if combat_events:
            return combat_events[0]
    pool = [e for e in cfg.events if e.depth_min <= depth <= e.depth_max]
    if not pool:                      # 该层无适配事件时回退到全部事件,避免探索中途崩溃
        pool = cfg.events
    weights = [e.weight for e in pool]
    return rng.choices(pool, weights=weights, k=1)[0]


def _pick_monster(cfg: GameConfig, depth: int, rng: random.Random):
    pool = [m for m in cfg.monsters.values()
            if m.depth_min <= depth <= m.depth_max]
    if not pool:
        # 超出所有怪物层数范围时,回退到层数范围最高的怪
        pool = [max(cfg.monsters.values(), key=lambda m: m.depth_max)]
    return rng.choice(pool)


def _consume_buffs(player: Player) -> None:
    """每成功走一步，所有 Buff 的 steps_left -= 1，归零移除。"""
    for b in player.buffs:
        b.steps_left -= 1
    player.buffs = [b for b in player.buffs if b.steps_left > 0]


def explore(player: Player, cfg: GameConfig, now: int,
            rng: random.Random) -> ExploreResult:
    b = cfg.balance
    stamina_mod.settle_stamina(player, now, b.stamina_regen_minutes, b.stamina_max,
                               b.stamina_regen_amount)
    player.last_active_at = now

    steps: list[StepLog] = []
    total_gold = total_exp = level_ups = 0
    items_gained: list[str] = []
    defeated = False
    depth_before = player.current_depth

    while player.stamina >= b.stamina_cost_per_step:
        player.stamina -= b.stamina_cost_per_step
        depth = player.current_depth
        event = _pick_event(cfg, depth, rng)

        if event.type == "combat":
            monster = _pick_monster(cfg, depth, rng)
            res = combat.resolve_combat(
                stats.attack(player, cfg), stats.defense(player, cfg),
                player.current_hp, monster, rng,
                player_lifesteal=stats.lifesteal(player, cfg),
                player_hp_max=stats.hp_max(player, cfg))
            player.current_hp = res.hp_after
            if not res.won:
                progression.apply_defeat(player, cfg)
                steps.append(StepLog(kind="combat", depth=depth,
                                     monster=monster.name, won=False,
                                     rounds=res.rounds, hp_after=player.current_hp))
                defeated = True
                break
            gold = int(rng.randint(monster.gold_min, monster.gold_max)
                       * (1 + stats.gold_bonus(player, cfg)))
            drops = loot.roll_drops(monster, rng)
            for item_id in drops:
                loot.add_item(player, item_id, cfg=cfg, rng=rng)
                items_gained.append(item_id)
            player.gold += gold
            ups = progression.grant_exp(player, monster.exp, cfg)
            level_ups += ups
            total_gold += gold
            total_exp += monster.exp
            player.current_depth += 1
            _consume_buffs(player)
            steps.append(StepLog(kind="combat", depth=depth, monster=monster.name,
                                 won=True, rounds=res.rounds, gold=gold,
                                 exp=monster.exp, items=drops,
                                 hp_after=player.current_hp))

        elif event.type == "treasure":
            lo, hi = event.reward_gold or (0, 0)
            gold = rng.randint(lo, hi)
            player.gold += gold
            total_gold += gold
            player.current_depth += 1
            _consume_buffs(player)
            steps.append(StepLog(kind="treasure", depth=depth,
                                 gold=gold, hp_after=player.current_hp))

        elif event.type == "trap":
            dmg = int(stats.hp_max(player, cfg) * (event.damage_pct or 0))
            player.current_hp -= dmg
            if player.current_hp <= 0:
                progression.apply_defeat(player, cfg)
                steps.append(StepLog(kind="trap", depth=depth,
                                     hp_after=player.current_hp,
                                     text=f"踩中陷阱 -{dmg}"))
                defeated = True
                break
            player.current_depth += 1
            _consume_buffs(player)
            steps.append(StepLog(kind="trap", depth=depth,
                                 hp_after=player.current_hp,
                                 text=f"踩中陷阱 -{dmg}"))

        else:  # flavor
            text = rng.choice(event.texts) if event.texts else ""
            player.current_depth += 1
            _consume_buffs(player)
            steps.append(StepLog(kind="flavor", depth=depth, text=text,
                                 hp_after=player.current_hp))

        player.max_depth = max(player.max_depth, player.current_depth)

    if steps:
        player.buffs.clear()
    return ExploreResult(
        steps=steps, total_gold=total_gold, total_exp=total_exp,
        items_gained=items_gained, level_ups=level_ups, defeated=defeated,
        stamina_left=player.stamina, depth_before=depth_before,
        depth_after=player.current_depth, hp_after=player.current_hp,
        hp_max=stats.hp_max(player, cfg),
    )
