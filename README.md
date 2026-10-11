# TG PanSou Bot

[English](README.en.md) · [安装与运维](docs/OPERATIONS.zh-CN.md) · [贡献](CONTRIBUTING.md) · [安全](SECURITY.md)

一个 Telegram 机器人：把你发来的关键词交给 [PanSou](https://github.com/Tumblr-code/pansou) 后端搜索，再把网盘资源按类型整理好发回来。

- 私聊和群聊都能搜索，结果按网盘类型分类、分页，可一键刷新
- 可选接入 TMDB，搜索影视时附带海报和简介
- 磁力链接只发给发起搜索的人；超长链接以文本文件发送，不截断
- 用 long polling 连接 Telegram，不需要公网 IP、域名或 HTTPS 证书
- 没有 HTTP 接口，也没有在线自更新命令；日志默认屏蔽 Token，不记录搜索词和用户 ID

## 开始之前

你需要准备四样东西：

1. **一台能访问 Telegram 的机器**，装有 Python 3.11 / 3.12，或者 Docker。访问不了 Telegram 时可以在配置里填代理。
2. **Bot Token**。在 Telegram 里找 [@BotFather](https://t.me/BotFather)，发送 `/newbot`，按提示起名，它会给你一串形如 `123456789:AA...` 的 Token。
3. **你自己的 Telegram 数字 ID**，用来把自己设为管理员。给任意一个「查询用户 ID」的机器人发消息就能拿到。
4. **一个正在运行的 PanSou 后端**。按 [PanSou 的教程](https://github.com/Tumblr-code/pansou#readme)在同一台机器上启动即可，默认地址是 `http://localhost:8888`。

## 五分钟上手

```bash
git clone https://github.com/Tumblr-code/tg-pansou-bot.git
cd tg-pansou-bot
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

用编辑器打开 `.env`，至少填这三项：

```env
TG_BOT_TOKEN=从 BotFather 拿到的 Token
PANSOU_API_URL=http://localhost:8888
ADMIN_IDS=你的数字 ID
```

然后启动：

```bash
.venv/bin/python main.py
```

在 Telegram 里给你的机器人发 `/start`，再发 `/search 关键词` 试一次搜索。按 `Ctrl+C` 停止。

> 同一个 Token 同一时间只能有一个实例在运行。再开第二个会报 `Conflict`，两边都收不到消息。

## 用 Docker 运行

```bash
git clone https://github.com/Tumblr-code/tg-pansou-bot.git
cd tg-pansou-bot
cp .env.example .env          # 同样填好上面三项
mkdir -p data && sudo chown 1000:1000 data && chmod 700 data
docker compose up -d --build
docker compose logs -f
```

容器以非 root 用户运行，根文件系统只读，用户设置保存在 `./data`。示例使用 host 网络，面向 Linux：后端地址写宿主机的 `http://localhost:8888` 即可。

想让它开机自启、崩溃自动重启，并且用专用系统账号运行，请看[安装与运维教程](docs/OPERATIONS.zh-CN.md)。

## 命令

| 命令 | 作用 | 谁能用 |
|---|---|---|
| `/search 关键词` | 搜索资源 | 所有人 |
| `/s 关键词` | 在群组里搜索 | 所有人 |
| `/help` | 查看帮助 | 所有人 |
| `/settings` | 查看或修改搜索设置 | 管理员 |
| `/types` | 查看支持的网盘类型 | 管理员 |
| `/sources`、`/plugins`、`/channels` | 查看来源、插件和频道 | 管理员 |
| `/filter` | 管理关键词过滤 | 管理员 |
| `/reset` | 重置搜索设置 | 管理员 |
| `/status` | 检查机器人和后端的状态 | 管理员 |
| `/refresh` | 刷新运行时缓存 | 管理员 |

没有填写 `ADMIN_IDS` 时，管理员命令对任何人都不开放。

## 配置

所有配置都写在 `.env` 里，完整示例和注释见 [.env.example](.env.example)。

| 变量 | 默认值 | 说明 |
|---|---|---|
| `TG_BOT_TOKEN` | 无，必填 | BotFather 给的 Token |
| `PANSOU_API_URL` | `http://localhost:8888` | PanSou 后端地址 |
| `PANSOU_API_TOKEN` | 空 | 后端开启认证时填写的 Bearer Token |
| `ADMIN_IDS` | 空 | 管理员数字 ID，多个用逗号分隔 |
| `DATA_DIR` | `./data` | 用户设置的保存目录 |
| `HTTP_PROXY` / `HTTPS_PROXY` | 空 | 访问 Telegram 和后端用的出口代理 |
| `MAX_CONCURRENT_SEARCHES` / `SEARCH_QUEUE_TIMEOUT` | `4` / `8` 秒 | 同时进行的搜索数和排队等待上限 |
| `SEARCH_TIMEOUT` / `MAX_KEYWORD_LENGTH` | `30` 秒 / `128` 字符 | 单次搜索超时和关键词长度上限 |
| `TMDB_READ_ACCESS_TOKEN` / `TMDB_API_KEY` | 空 | 可选，填其中一个即可启用影视信息 |
| `DROP_PENDING_UPDATES` | `false` | 启动时是否丢弃离线期间积压的消息 |
| `APP_VERSION` | `dev` | 显示在 `/status` 里的版本标识 |

## 常见问题

- **启动报 `Conflict` / `getUpdates`**：同一个 Token 还有别的实例在运行，先把它停掉。
- **能收到消息但搜不到结果**：先确认后端正常，`curl http://localhost:8888/api/health` 应返回 `"status":"ok"`；再检查 `PANSOU_API_URL`、代理和认证 Token。
- **管理员命令没反应**：`ADMIN_IDS` 没填，或者填的不是你自己的数字 ID。
- **影视信息不显示**：TMDB 凭据没填或无法访问 TMDB。这不影响普通资源搜索。
- **设置保存失败**：检查 `DATA_DIR` 是否存在，以及运行机器人的用户能否写入。

更多排查步骤、升级回退和备份恢复见[安装与运维教程](docs/OPERATIONS.zh-CN.md)。

## 安全提醒

- Token 就是机器人的密码。不要提交到 Git、打进镜像、贴到 issue 或聊天里；泄露后立刻在 BotFather 用 `/revoke` 换新。
- `.env` 建议设为仅自己可读：`chmod 600 .env`。
- PanSou 后端默认没有认证，只应监听本机地址，不要把 8888 端口暴露到公网。

## 开发

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python scripts/verify_source_manifest.py
.venv/bin/python scripts/secret_scan.py
.venv/bin/ruff check .
.venv/bin/pytest -q
.venv/bin/python scripts/smoke_test.py
.venv/bin/python -m pip check
```

测试全部使用模拟数据和模拟网络客户端，不需要真实 Token，也不会向 Telegram 发送消息。改动 `main.py`、`requirements.txt` 或 `src/` 后，运行 `scripts/verify_source_manifest.py --update` 更新[源码清单](docs/SOURCE_MANIFEST.json)。`scripts/package_release.py --version vX.Y.Z` 可以打出只含源码、模板和文档的发行包。

## 许可

本仓库目前没有声明项目许可证。PanSou 后端采用 MIT 许可证，但那不等于本项目的授权；各依赖遵循各自的许可证，见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
