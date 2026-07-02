# NapCat OneBot v11 环境配置

本文档面向 Windows 下的 NapCat Shell 包，示例路径：

```text
D:\QQBot\NapCat.Shell
```

目标链路：

```text
QQ 群消息
  -> NapCat 普通 QQ 号
  -> OneBot v11 反向 WebSocket
  -> NoneBot2
  -> qq-idle-rpg 游戏逻辑
  -> QQ 群回复
```

## 1. 准备项目环境

在 RPG 项目目录安装依赖：

```bash
cd "D:\Claude Code\qq-idle-rpg"
python -m pip install -e ".[dev]"
```

复制 OneBot 配置模板：

```bash
copy .env.onebot.example .env
```

默认 `.env.onebot.example` 会让 NoneBot 监听本机 `8080` 端口：

```dotenv
DRIVER=~fastapi+~websockets
HOST=127.0.0.1
PORT=8080
COMMAND_START=["", "/"]
NICKNAME=["挂机RPG"]
```

## 2. 启动 RPG Bot

在 RPG 项目目录运行：

```bash
python -m bot.__main_onebot__
```

保持这个窗口运行。看到插件加载成功即可，例如：

```text
Succeeded to load plugin "rpg" from "bot.plugins.rpg"
```

## 3. 配置 NapCat OneBot v11

账号配置文件通常位于：

```text
D:\QQBot\NapCat.Shell\config\onebot11_<QQ号>.json
```

例如：

```text
D:\QQBot\NapCat.Shell\config\onebot11_2373037274.json
```

把 `network.websocketClients` 配置为连接 RPG Bot：

```json
{
  "network": {
    "httpServers": [],
    "httpSseServers": [],
    "httpClients": [],
    "websocketServers": [],
    "websocketClients": [
      {
        "name": "qq-idle-rpg",
        "enable": true,
        "url": "ws://127.0.0.1:8080/onebot/v11/ws",
        "messagePostFormat": "array",
        "reportSelfMessage": false,
        "reconnectInterval": 5000,
        "token": "",
        "debug": false,
        "heartInterval": 30000
      }
    ],
    "plugins": []
  },
  "musicSignUrl": "",
  "enableLocalFile2Url": false,
  "parseMultMsg": false,
  "imageDownloadProxy": "",
  "timeout": {
    "baseTimeout": 10000,
    "uploadSpeedKBps": 256,
    "downloadSpeedKBps": 256,
    "maxTimeout": 1800000
  }
}
```

也可以通过 NapCat WebUI 配置：

```text
http://127.0.0.1:6099
```

WebUI token 在：

```text
D:\QQBot\NapCat.Shell\config\webui.json
```

新增网络配置：

```text
类型: Websocket客户端
名称: qq-idle-rpg
启用: 开
URL: ws://127.0.0.1:8080/onebot/v11/ws
消息格式: array
上报自身消息: 关
Token: 留空
重连间隔: 5000
心跳间隔: 30000
```

## 4. 启动 NapCat

在 NapCat 目录运行：

```text
D:\QQBot\NapCat.Shell\launcher-user.bat
```

推荐启动顺序：

1. 先启动 `python -m bot.__main_onebot__`
2. 再启动 NapCat
3. NapCat 登录普通 QQ 号
4. NapCat 自动连接 `ws://127.0.0.1:8080/onebot/v11/ws`

## 5. 群里测试

在 QQ 群里发送：

```text
@机器人 注册 小明
@机器人 状态
@机器人 探索
@机器人 背包
@机器人 商店
@机器人 购买 金疮药
@机器人 出售装备
@机器人 前往 35
@机器人 前往 最深
@机器人 排行榜
```

私聊可直接发送：

```text
注册 小明
探索
状态
```

## 6. 常见问题

### 群里没反应

优先确认消息里是否 `@机器人`。当前命令都使用 `to_me()` 规则，群聊里需要让 NoneBot 判断消息是发给机器人的。

### RPG Bot 没看到 NapCat 连接

检查：

- `python -m bot.__main_onebot__` 是否正在运行
- `.env` 里的 `PORT` 是否为 `8080`
- NapCat 的 WebSocket URL 是否为 `ws://127.0.0.1:8080/onebot/v11/ws`
- 防火墙是否阻止本地连接

### NapCat 和 RPG Bot 不在同一台机器

RPG Bot 的 `.env` 改为：

```dotenv
HOST=0.0.0.0
PORT=8080
```

NapCat 的 URL 改为：

```text
ws://你的服务器IP:8080/onebot/v11/ws
```

### 改代码后没生效

重启 RPG Bot：

```bash
python -m bot.__main_onebot__
```

通常不需要重启 NapCat，除非修改了 NapCat 自己的配置。
