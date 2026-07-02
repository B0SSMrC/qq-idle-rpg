# QQ Idle RPG Bot

基于 NoneBot2 + OneBot v11 的 QQ 群文字挂机 RPG。当前项目只保留普通 QQ 号协议端接入方式，例如 NapCatQQ 或 Lagrange.OneBot。

## 快速开始

### 1. 安装依赖

```bash
pip install -e ".[dev]"
```

### 2. 配置 OneBot

复制 OneBot 配置模板：

```bash
cp .env.onebot.example .env
```

默认监听地址：

```dotenv
DRIVER=~fastapi+~websockets
HOST=127.0.0.1
PORT=8080
COMMAND_START=["", "/"]
NICKNAME=["挂机RPG"]
```

### 3. 启动机器人

```bash
python -m bot.__main_onebot__
```

### 4. 配置协议端

在 NapCatQQ / Lagrange.OneBot 中启用 OneBot v11，并配置反向 WebSocket：

```text
ws://127.0.0.1:8080/onebot/v11/ws
```

详细步骤见 [NapCat 环境配置](docs/napcat-environment-setup.md)。

## 身份与存档

- 群聊：`group_id = 群号`，`user_id = QQ 号`
- 私聊：`group_id = "private"`，`user_id = QQ 号`

机器人按照群号区分世界，同一个玩家在不同群中拥有独立角色。

## 指令

群聊中建议 `@机器人 指令`，私聊中可以直接发送指令。

| 指令 | 说明 |
|------|------|
| `注册 名字` | 创建角色 |
| `探索` | 下潜冒险，消耗体力获得经验/金币/装备 |
| `状态` | 查看角色面板 |
| `背包` | 查看持有物品 |
| `装备 物品名` | 装备武器或防具 |
| `卸下 物品名` | 卸下装备 |
| `使用 物品名` | 使用消耗品 |
| `商店` | 查看在售物品及价格 |
| `购买 物品名` | 购买物品 |
| `出售装备` | 一键出售未装备武器/防具 |
| `前往 35` | 回到已探索过的层数刷资源 |
| `前往 最深` | 回到历史最深层继续推进 |
| `排行榜` | 当前世界等级榜 |
| `排行榜 深度` | 当前世界最深层榜 |
| `帮助` | 查看完整指令菜单 |

## 项目结构

```text
game_core/   纯逻辑层：战斗、探索、装备、商店
storage/     SQLite 持久层
app/         服务层：组合游戏逻辑与持久化
bot/         OneBot 启动入口、运行状态和命令处理
data/        YAML 配置：balance、monsters、events、items
tests/       自动化测试
```

## 测试

```bash
python -m pytest -q
```
