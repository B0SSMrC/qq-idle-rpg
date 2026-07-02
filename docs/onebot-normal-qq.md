# OneBot v11 普通 QQ 号接入方案

本项目只保留 OneBot v11 接入。协议端负责登录 QQ 号、接收消息并转成 OneBot 事件；本项目负责识别指令、执行 RPG 规则、读写 SQLite 存档并回复。

## 架构

```text
QQ 群/私聊
  -> NapCatQQ / Lagrange.OneBot
  -> OneBot v11 反向 WebSocket
  -> NoneBot2 + nonebot-adapter-onebot
  -> bot.plugins.rpg
  -> app.services
  -> game_core + SQLite
```

## 安装

```bash
pip install -e ".[dev]"
```

## 配置

复制模板：

```bash
cp .env.onebot.example .env
```

默认 `.env`：

```dotenv
DRIVER=~fastapi+~websockets
HOST=127.0.0.1
PORT=8080
COMMAND_START=["", "/"]
NICKNAME=["挂机RPG"]
```

## 启动

```bash
python -m bot.__main_onebot__
```

启动后，NoneBot 会在 `127.0.0.1:8080` 等待协议端连接。

## 协议端连接

在 NapCatQQ / Lagrange.OneBot 中启用 OneBot v11，并配置反向 WebSocket：

```text
ws://127.0.0.1:8080/onebot/v11/ws
```

如果协议端和本项目不在同一台机器，把 `.env` 中的 `HOST` 改成：

```dotenv
HOST=0.0.0.0
```

协议端连接地址改成：

```text
ws://你的服务器IP:8080/onebot/v11/ws
```

## 存档范围

- 群聊：`group_id = 群号`，`user_id = QQ 号`
- 私聊：`group_id = "private"`，`user_id = QQ 号`

同一个玩家在不同群中拥有不同角色和排行榜进度。

## 测试指令

群聊：

```text
@机器人 注册 小明
@机器人 探索
@机器人 状态
@机器人 背包
@机器人 商店
@机器人 出售装备
@机器人 排行榜
```

私聊：

```text
注册 小明
探索
状态
```

## 常见问题

### 群里发指令没有反应

当前命令都使用 `to_me()` 规则。群聊里优先使用 `@机器人 探索`，并确认协议端上报的消息包含机器人被提及的信息。

### 私聊能用，群聊不能用

检查协议端是否上报群消息、机器人是否在群内、反向 WebSocket 是否已连接。

### 修改代码后没生效

重启 RPG Bot：

```bash
python -m bot.__main_onebot__
```
