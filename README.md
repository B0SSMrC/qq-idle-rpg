# QQ 挂机探索 RPG 机器人

基于 NoneBot2 的 QQ 群文字挂机 RPG。

支持两种接入方式:
- QQ 官方机器人: `nonebot-adapter-qq`,适合沙箱/正式合规上线。
- 普通 QQ 号协议端: `nonebot-adapter-onebot` + OneBot v11,适合自用/内测。

## 快速开始

### 1. 安装依赖

```bash
pip install -e ".[dev]"
```

### 2. 方式 A:配置 QQ 官方机器人凭据

将 `.env.example` 复制为 `.env`,然后填入沙箱机器人信息:

```bash
cp .env.example .env
```

打开 [q.qq.com](https://q.qq.com) → 开发者中心 → 你的应用 → 开发设置,
获取 **AppID**、**Token**（机器人令牌）和 **AppSecret**,填入 `.env`:

```dotenv
DRIVER=~fastapi+~httpx+~websockets
COMMAND_START=["", "/"]
QQ_IS_SANDBOX=true
QQ_BOTS='[{"id": "你的AppID", "token": "你的Token", "secret": "你的AppSecret", "intent": {"c2c_group_at_messages": true}}]'
```

关键点(踩坑必看):
- **`DRIVER` 三段**:QQ 适配器要 HTTP + WebSocket 客户端。
- **`QQ_IS_SANDBOX=true`**:沙箱阶段必须开,否则连正式环境、收不到沙箱消息。
- **`intent.c2c_group_at_messages=true`**:接收「单聊/群」消息的开关,**默认是关的**,不开则机器人收不到任何单聊/群消息。
- **`COMMAND_START` 含空字符串**:让「注册」等裸关键词(无 `/`)能触发;群/频道仍需 @机器人,单聊直接发。

### 3. 运行

```bash
python -m bot
```

### 4. 方式 B:普通 QQ 号 / OneBot v11

普通 QQ 号模式不使用 QQ 开放平台凭据。你需要先准备一个 OneBot v11 协议端
(如 NapCatQQ / Lagrange.OneBot),由协议端登录 QQ 号并连接本项目。

复制 OneBot 配置模板:

```bash
cp .env.onebot.example .env
```

启动本项目的 OneBot 入口:

```bash
python -m bot.__main_onebot__
```

然后在协议端里配置反向 WebSocket:

```text
ws://127.0.0.1:8080/onebot/v11/ws
```

普通 QQ 号模式说明:
- 群聊里建议 `@机器人 探索`;私聊可直接发 `探索`。
- 群聊存档范围使用 OneBot 的 `group_id`;私聊使用固定世界 `"private"`。
- 该方式不是 QQ 开放平台官方机器人路径,适合小范围自用/内测。

详细 NapCat 配置见 `docs/napcat-environment-setup.md`。

### 5. 在 QQ 沙箱频道/群 或 OneBot 群聊中测试

@ 机器人发送以下指令验证各功能:

| 指令 | 说明 |
|------|------|
| `注册 名字` | 创建角色 |
| `探索` | 下潜冒险,消耗体力获得经验/金币/装备 |
| `状态` | 查看角色面板(HP、体力、装备、战力) |
| `背包` | 查看持有物品 |
| `商店` | 查看在售物品及价格 |
| `购买 金疮药` | 购买物品 |
| `出售装备` | 一键出售未装备武器/防具 |
| `排行榜` | 当前世界等级榜 |
| `排行榜 深度` | 当前世界最深层榜 |
| `帮助` | 查看完整指令菜单 |

## 项目结构

```
game_core/   — 纯逻辑层(战斗/探索/装备/商店)
storage/     — SQLite 持久层
app/         — 服务层(组合逻辑 + 持久化)
bot/
  state.py           — 进程级单例(DB连接、配置、异步锁)
  plugins/rpg.py     — NoneBot2 命令处理器
  __main__.py        — QQ 官方机器人启动入口
  __main_onebot__.py — 普通 QQ 号 / OneBot v11 启动入口
data/        — YAML 配置(balance/monsters/events/items)
```

## 运行测试

```bash
python -m pytest -q
```
