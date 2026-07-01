"""OneBot v11 启动入口 — python -m bot.__main_onebot__

用于普通 QQ 号协议端（如 NapCatQQ / Lagrange.OneBot）接入。
协议端负责登录 QQ 并把消息转成 OneBot v11 事件；本进程只负责接收事件、
执行 RPG 逻辑并回复。
"""
import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter

nonebot.init()

driver = nonebot.get_driver()
driver.register_adapter(OneBotV11Adapter)

nonebot.load_plugin("bot.plugins.rpg")

if __name__ == "__main__":
    nonebot.run()
