# 普通 QQ 号 / OneBot v11 接入方案

> 该方案用于自用或小范围内测。它不是 QQ 开放平台官方机器人路径，稳定性和账号风险取决于你使用的协议端与 QQ 风控。

## 架构

```text
普通 QQ 号
  ↓
NapCatQQ / Lagrange.OneBot 等协议端
  ↓ OneBot v11 反向 WebSocket
NoneBot2 + nonebot-adapter-onebot
  ↓
bot.plugins.rpg
  ↓
app.services → game_core + SQLite
```

协议端只负责登录 QQ、收发消息、转换 OneBot 事件。本项目负责游戏命令、存档、战斗、商店、排行榜。

## 安装依赖

```bash
pip install -e ".[dev]"
```

`pyproject.toml` 已包含 `nonebot-adapter-onebot`。

## 配置本项目

复制模板:

```bash
cp .env.onebot.example .env
```

默认配置:

```dotenv
DRIVER=~fastapi+~websockets
HOST=127.0.0.1
PORT=8080
COMMAND_START=["", "/"]
NICKNAME=["挂机RPG"]
```

启动:

```bash
python -m bot.__main_onebot__
```

启动后，NoneBot 会在本机 `127.0.0.1:8080` 等待协议端连接。

## 配置协议端

在 NapCatQQ / Lagrange.OneBot 中启用 OneBot v11，并配置反向 WebSocket:

```text
ws://127.0.0.1:8080/onebot/v11/ws
```

如果协议端和本项目不在同一台机器:

```text
ws://你的服务器IP:8080/onebot/v11/ws
```

同时把 `.env` 里的 `HOST` 改为:

```dotenv
HOST=0.0.0.0
```

如果设置了 access token，请确保协议端和 NoneBot 两侧 token 一致。

## 测试指令

群聊中:

```text
@机器人 注册 小明
@机器人 探索
@机器人 状态
@机器人 商店
@机器人 购买 金疮药
@机器人 排行榜
```

私聊中:

```text
注册 小明
探索
状态
```

## 存档范围

- OneBot 群聊: `group_id = 群号`, `user_id = QQ 号`
- OneBot 私聊: `group_id = "private"`, `user_id = QQ 号`
- QQ 官方机器人群聊/频道/私聊仍按官方 openid 规则存档

因此普通 QQ 号模式和官方机器人模式即使共用 `rpg.db`，同一个玩家也通常不会撞到同一份存档。

## 常见问题

### 群里发指令没反应

优先使用 `@机器人 探索`。当前插件所有命令都带 `to_me()` 规则，群聊里需要让 NoneBot 判断消息是发给机器人的。

### 私聊能用，群聊不能用

检查协议端是否上报群消息、机器人是否在群内、反向 WebSocket 是否已连接。

### `/购买 金疮药` 找不到物品

项目已兼容 `/` 前缀；如果仍失败，确认协议端上报的纯文本是不是包含额外空格、昵称或 CQ 码。

### 能不能和 QQ 官方机器人同时跑

可以，但建议使用不同进程和不同 `.env`。如果共用 `rpg.db`，需要避免两个进程同时高频写入同一数据库。
