from game_core.models import (
    InventoryItem, Player, make_new_player,
    MonsterDef, DropDef, EventDef, ItemDef, Balance, GameConfig,
    CombatResult, StepLog, ExploreResult,
)


def test_make_new_player_defaults():
    p = make_new_player("g1", "u1", "勇者", now=1000, start_hp=100)
    assert p.group_id == "g1"
    assert p.user_id == "u1"
    assert p.name == "勇者"
    assert p.level == 1
    assert p.current_hp == 100        # 新角色满血
    assert p.current_depth == 1
    assert p.max_depth == 1
    assert p.stamina == 0
    assert p.stamina_at == 1000
    assert p.inventory == []


def test_inventory_item_defaults():
    it = InventoryItem(item_id="hp_potion")
    assert it.quantity == 1
    assert it.equipped is False


def test_dataclasses_constructible():
    # 仅验证这些结构能被构造且字段存在
    DropDef(item="x", chance=0.1)
    MonsterDef(id="m", name="怪", depth_min=1, depth_max=5, hp=10,
               atk=1, defense=1, exp=5, gold_min=1, gold_max=2, drops=[])
    EventDef(id="e", type="flavor", weight=10)
    ItemDef(id="i", name="物", slot="weapon")
    Balance(stamina_regen_minutes=5, stamina_max=50, stamina_cost_per_step=5,
            base_exp=100, growth=1.4, stats_hp=20, stats_atk=3, stats_def=2,
            base_hp=100, base_atk=10, base_def=5, gold_loss_pct=0.1)
    CombatResult(won=True, rounds=2, damage_taken=5, hp_after=95)
    StepLog(kind="flavor", depth=2)
    ExploreResult(steps=[], total_gold=0, total_exp=0, items_gained=[],
                  level_ups=0, defeated=False, stamina_left=0,
                  depth_before=1, depth_after=1, hp_after=100, hp_max=100)
