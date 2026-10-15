# PanSou Bot

[English](README.en.md) · [安装与运维](docs/OPERATIONS.zh-CN.md) · [贡献](CONTRIBUTING.md) · [安全](SECURITY.md)

一个网盘资源搜索 Telegram 机器人。它把 [PanSou](https://github.com/fish2018/pansou) 搜索引擎和 Telegram 机器人整合成一个项目：一个 Docker 镜像，填好 Token 就能用，搜索引擎还能在 Telegram 里一键在线升级。

- 私聊和群聊都能搜索，结果按网盘类型分类、分页，可一键刷新
- 一个容器就是全部，没有别的服务要部署或维护
- 在线升级：每天自动从上游源码编译新版搜索引擎；管理员发 `/upgrade` 即可升级，失败自动恢复，也能一键回滚
- 可选接入 TMDB，搜索影视时附带海报和简介
- 磁力链接只发给发起搜索的人；超长链接以文本文件发送，不截断
- 用 long polling 连接 Telegram，不需要公网 IP、域名或 HTTPS 证书

## 开始之前

你需要准备三样东西：

1. **一台能访问 Telegram 的 Linux 机器**，装好 Docker（含 Compose 插件），x86_64 或 ARM64 都可以。访问不了 Telegram 时可以在配置里填代理。
2. **Bot Token**。在 Telegram 里找 [@BotFather](https://t.me/BotFather)，发送 `/newbot`，按提示起名，它会给你一串形如 `123456789:AA...` 的 Token。
3. **你自己的 Telegram 数字 ID**，用来把自己设为管理员。给任意一个「查询用户 ID」的机器人发消息就能拿到。

## 五分钟上手

```bash
git clone https://github.com/Tumblr-code/pansou-bot.git
cd pansou-bot
cp .env.example .env
```

用编辑器打开 `.env`，填这两项：

```env
TG_BOT_TOKEN=从 BotFather 拿到的 Token
ADMIN_IDS=你的数字 ID
```

准备数据目录（容器里的程序以 UID 1000 运行），然后启动：

```bash
mkdir -p data && sudo chown 1000:1000 data
docker compose pull
docker compose up -d
docker compose logs -f
```

`docker compose pull` 拉取已经构建好的镜像（amd64 / arm64）。想用本地源码自己构建，跳过它，改用 `docker compose up -d --build`，第一次构建要编译搜索引擎，需要几分钟。

日志里出现 `engine_ready` 和 `telegram_api_connected` 就说明启动好了。在 Telegram 里给机器人发 `/start`，再发一个关键词试试搜索。

> 同一个 Token 同一时间只能有一个实例在运行。再开第二个会报 `Conflict`，两边都收不到消息。

## 在线升级

PanSou 搜索引擎更新很频繁（经常增删数据源）。本仓库的 GitHub Actions 每天检查一次上游，有新提交就从源码编译 amd64 / arm64 两个版本，连同 SHA256 校验文件发布到 [Releases](https://github.com/Tumblr-code/pansou-bot/releases)。

| 操作 | 方法 |
|---|---|
| 查看搜索引擎版本和状态 | 发送 `/status` |
| 检查并升级 | 发送 `/upgrade`，有新版本时点「立即升级」 |
| 退回上一个版本 | 发送 `/upgrade rollback` |
| 有新版本时自动提醒 | 默认每 24 小时检查一次，有新版会私信所有管理员 |
| 全自动升级 | 在 `.env` 里设 `AUTO_UPGRADE=true` |

升级过程：下载 → 核对 SHA256 → 启动新版本 → 通过健康检查后才替换。新版本起不来时，原版本会继续运行，这个版本也会被记下来不再提醒。升级下载的版本保存在 `data/engine/`，容器重启或重建后依然生效。

机器人自身的代码随镜像更新：`docker compose pull && docker compose up -d`。

## 命令

| 命令 | 作用 | 谁能用 |
|---|---|---|
| `/search 关键词` | 搜索资源（私聊里直接发关键词也行） | 所有人 |
| `/s 关键词` | 在群组里搜索 | 所有人 |
| `/help` | 查看帮助 | 所有人 |
| `/settings` | 查看或修改搜索设置 | 管理员 |
| `/types` | 查看支持的网盘类型 | 管理员 |
| `/sources`、`/plugins`、`/channels` | 查看来源、插件和频道 | 管理员 |
| `/filter` | 管理关键词过滤 | 管理员 |
| `/reset` | 重置搜索设置 | 管理员 |
| `/status` | 查看运行状态和搜索引擎版本 | 管理员 |
| `/refresh` | 刷新运行时缓存 | 管理员 |
| `/upgrade` | 在线升级搜索引擎；`/upgrade rollback` 回滚 | 管理员 |

没有填写 `ADMIN_IDS` 时，管理员命令对任何人都不开放。

## 配置

所有配置都写在 `.env` 里，完整示例和注释见 [.env.example](.env.example)。常用的几项：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `TG_BOT_TOKEN` | 无，必填 | BotFather 给的 Token |
| `ADMIN_IDS` | 空 | 管理员数字 ID，多个用逗号分隔 |
| `HTTP_PROXY` / `HTTPS_PROXY` | 空 | 出口代理，访问 Telegram、GitHub 和各个搜索来源时使用 |
| `UPGRADE_CHECK_HOURS` | `24` | 多久检查一次新版本，`0` 关闭 |
| `AUTO_UPGRADE` | `false` | 发现新版本时直接升级，而不是只提醒 |
| `CHANNELS` / `ENABLED_PLUGINS` | 跟随上游 | 搜索的 TG 频道和插件，逗号分隔；留空使用上游的默认列表 |
| `TMDB_READ_ACCESS_TOKEN` / `TMDB_API_KEY` | 空 | 可选，填其中一个即可启用影视信息 |

PanSou 自己的配置项（缓存、并发、超时等，见[上游文档](https://github.com/fish2018/pansou#readme)）直接写进同一个 `.env` 就会生效。Bot Token 和 TMDB 凭据只给机器人用，不会交给搜索引擎进程。

## 常见问题

- **启动报 `Conflict` / `getUpdates`**：同一个 Token 还有别的实例在运行，先把它停掉。
- **日志里有 `PermissionError` / 设置保存失败**：`data` 目录不属于 UID 1000，执行 `sudo chown -R 1000:1000 data`。
- **能收到消息但搜不到结果**：发 `/status` 看搜索引擎是否正常；不正常时看 `docker compose logs` 里 `engine_` 开头的日志。
- **`/upgrade` 提示无法访问 GitHub**：机器需要能访问 `api.github.com` 和 `github.com`，必要时在 `.env` 里配置 `HTTPS_PROXY`。
- **管理员命令没反应**：`ADMIN_IDS` 没填，或者填的不是你自己的数字 ID。
- **影视信息不显示**：TMDB 凭据没填或无法访问 TMDB。这不影响普通资源搜索。

更多内容（备份恢复、不用 Docker 的运行方式）见[安装与运维教程](docs/OPERATIONS.zh-CN.md)。

## 安全提醒

- Token 就是机器人的密码。不要提交到 Git、打进镜像、贴到 issue 或聊天里；泄露后立刻在 BotFather 用 `/revoke` 换新。
- `.env` 建议设为仅自己可读：`chmod 600 .env`。
- 容器不需要也不应该映射任何端口。
- 在线升级只从 `UPGRADE_REPO` 指定的仓库下载，并核对 SHA256；每个发布还附带 GitHub 构建来源证明，可以用 `gh attestation verify` 验证。

## 开发

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python scripts/secret_scan.py
.venv/bin/ruff check .
.venv/bin/pytest -q
.venv/bin/python scripts/smoke_test.py
```

测试全部使用模拟数据：Telegram 和 GitHub 都是模拟的，搜索引擎用一个假的可执行文件代替，不需要真实 Token，也不需要 Go 或 Docker。

目录结构：

```text
main.py, src/            Python 代码；src/engine_*.py 负责运行和升级搜索引擎
engine/UPSTREAM          镜像使用的上游 PanSou 版本
engine/build.sh          从上游源码编译搜索引擎（Dockerfile 和发布工作流都用它）
scripts/bump_engine.sh   把镜像使用的版本更新到上游最新提交
```

## 许可

本仓库目前没有声明项目许可证。PanSou 搜索引擎来自 [fish2018/pansou](https://github.com/fish2018/pansou)，采用 MIT 许可证，镜像和发布包里都附带了它的 LICENSE；这不等于本项目的授权。各依赖遵循各自的许可证，见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
