"""game_rpg_mcp — 把 QQ 文字挂机 RPG 引擎暴露为 MCP 工具。

LLM 智能体(如 OpenClaw)通过这些工具游玩游戏:数值/存档/挂机/排行由 game_core
权威计算,LLM 只负责听懂人话与叙事。工具在后续任务中添加。
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("game_rpg_mcp")
