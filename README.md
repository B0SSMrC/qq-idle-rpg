# QQ 挂机探索 RPG 机器人

基于 NoneBot2 + nonebot-adapter-qq 的 QQ 群文字挂机 RPG。

## 快速开始

### 1. 安装依赖

```bash
pip install -e ".[dev]"
```

### 2. 配置 QQ 机器人凭据

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

### 4. 在 QQ 沙箱频道/群 中测试

@ 机器人发送以下指令验证各功能:

| 指令 | 说明 |
|------|------|
| `注册 名字` | 创建角色 |
| `探索` | 下潜冒险,消耗体力获得经验/金币/装备 |
| `状态` | 查看角色面板(HP、体力、装备、战力) |
| `背包` | 查看持有物品 |
| `商店` | 查看在售物品及价格 |
| `购买 治疗药水` | 购买物品 |
| `排行榜` | 本群等级榜 |
| `排行榜 深度` | 本群最深层榜 |
| `帮助` | 查看完整指令菜单 |

## 项目结构

```
game_core/   — 纯逻辑层(战斗/探索/装备/商店)
storage/     — SQLite 持久层
app/         — 服务层(组合逻辑 + 持久化)
bot/
  state.py           — 进程级单例(DB连接、配置、异步锁)
  plugins/rpg.py     — NoneBot2 命令处理器
  __main__.py        — 启动入口
data/        — YAML 配置(balance/monsters/events/items)
```

## 运行测试

```bash
python -m pytest -q
```
