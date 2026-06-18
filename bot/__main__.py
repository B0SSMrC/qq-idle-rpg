"""Bot 启动入口 — python -m bot

从项目根目录的 .env 文件读取 DRIVER / QQ_BOTS 等配置,
注册 QQ 适配器,加载 RPG 插件,然后运行。

.env 示例 (复制 .env.example):
    DRIVER=~fastapi+~httpx
    QQ_BOTS='[{"id":"AppID","token":"Token","secret":"Secret"}]'
"""
import nonebot
from nonebot.adapters.qq import Adapter as QQAdapter

nonebot.init()

driver = nonebot.get_driver()
driver.register_adapter(QQAdapter)

nonebot.load_plugin("bot.plugins.rpg")

if __name__ == "__main__":
    nonebot.run()
