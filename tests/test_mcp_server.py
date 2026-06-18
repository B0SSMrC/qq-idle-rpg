import os
os.environ["GAME_RPG_DB"] = ":memory:"

import asyncio
from mcp_server import server

EXPECTED_TOOLS = {
    "rpg_register", "rpg_status", "rpg_inventory", "rpg_explore",
    "rpg_equip", "rpg_unequip", "rpg_use_item", "rpg_shop",
    "rpg_buy", "rpg_ranking",
}


def test_all_tools_registered():
    names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert EXPECTED_TOOLS <= names, f"missing: {EXPECTED_TOOLS - names}"


def test_end_to_end_register_status_explore():
    # 直接调用工具函数验证 wiring(FastMCP @mcp.tool() 返回原函数,仍可直接调用)
    reg = server.rpg_register(world_id="w_e2e", player_id="u", name="冒烟侠")
    assert reg["ok"] is True, reg
    assert reg["player"]["name"] == "冒烟侠"

    st = server.rpg_status(world_id="w_e2e", player_id="u")
    assert st["ok"] is True
    assert st["player"]["name"] == "冒烟侠"

    shop = server.rpg_shop()
    assert shop["ok"] is True and any(i["name"] == "金疮药" for i in shop["items"])


def test_error_surfaces_as_ok_false():
    res = server.rpg_status(world_id="w_err", player_id="ghost")
    assert res["ok"] is False and "error" in res
