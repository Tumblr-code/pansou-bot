# PanSou Bot 安装与运维

[English](OPERATIONS.en.md) · [首页](../README.md)

这份教程讲长期运行时会用到的内容：容器里有什么、数据放在哪、怎样升级和回滚、怎样备份，以及不用 Docker 时怎么装。只想先跑起来，看[首页的五分钟上手](../README.md#五分钟上手)就够了。

## 容器里有什么

```text
tini                     PID 1，转发信号、回收子进程
└─ python main.py        机器人
   └─ pansou             PanSou 后端，只监听容器内部的 8888 端口
```

机器人启动时先拉起后端，等它通过健康检查（`/api/health`）再开始收消息。后端意外退出会自动重启，间隔从 1 秒逐步拉长到 30 秒。在线升级后的新版本如果两分钟内连续崩溃三次，会自动退回上一个版本。

镜像的根文件系统是只读的，所有可写内容都在挂载到 `/data` 的目录里：

```text
data/
├─ user_settings.json        用户的搜索设置
└─ backend/
   ├─ state.json             当前后端版本、上一个版本、启动失败过的版本
   ├─ releases/<提交号>/      在线升级下载的后端（最多保留两个）
   ├─ cache/                 后端的搜索缓存
   └─ work/                  后端的工作目录
```

镜像自带的后端在 `/opt/pansou/`，版本记录在仓库的 `backend/UPSTREAM` 里。`data/backend/state.json` 不存在或指向的版本不可用时，就运行镜像自带的版本。

## 日常操作

```bash
docker compose logs -f --tail=100     # 看日志
docker compose restart                # 重启
docker compose down                   # 停止并删除容器（data 目录不受影响）
docker compose ps                     # 状态；HEALTHY 表示后端健康检查通过
```

日志是 JSON 格式。机器人默认不记录搜索词和用户 ID，Token 会被屏蔽；后端的日志原样输出。

## 升级

**后端**：在 Telegram 里发 `/upgrade`，详见[首页](../README.md#在线升级后端)。不想用在线升级，把 `BACKEND_UPDATE_CHECK_HOURS` 设为 `0`，然后靠更新镜像升级。

**机器人和镜像自带的后端**：

```bash
docker compose pull
docker compose up -d
```

自己构建的用 `git pull && docker compose up -d --build`。

如果在线升级过的版本比新镜像自带的还新，容器重建后仍然运行在线升级的版本。想改回镜像自带的版本，发 `/upgrade rollback` 直到 `/backend` 显示「镜像自带」，或者停掉容器后删除 `data/backend/state.json`。

**回滚镜像**：`.env` 同目录下的 `docker-compose.yml` 里把 `image:` 改成某个 `sha-<提交号>` 标签，再 `docker compose up -d`。可用的标签在仓库的 Packages 页面。

## 备份与恢复

需要备份的只有两样：`.env` 和 `data/user_settings.json`。`data/backend/` 里都是可以重新下载或重新生成的内容。

```bash
tar -czf pansou-bot-backup-$(date +%F).tar.gz .env data/user_settings.json
```

恢复：停掉容器，把这两个文件放回原处，确认 `data` 属于 UID 1000，再启动。

## 后端配置

`.env` 里的变量会原样传给后端，只有 `TG_BOT_TOKEN`、`TMDB_READ_ACCESS_TOKEN`、`TMDB_API_KEY` 例外。`PORT` 和 `CACHE_PATH` 由机器人固定设置。

`CHANNELS`、`ENABLED_PLUGINS` 等留空时，使用当前后端版本附带的默认值（来自上游 Dockerfile，保存在每个版本的 `defaults.env` 里）。这样升级后端时，上游新增或移除的插件会自动跟上；自己填了就以你的为准。

## 后端相关的全部设置

| 变量 | 默认值 | 说明 |
|---|---|---|
| `BACKEND_PORT` | `8888` | 后端在容器内监听的端口，只有机器人访问 |
| `BACKEND_START_TIMEOUT` | `60` | 等待后端通过健康检查的秒数 |
| `BACKEND_UPDATE_REPO` | `Tumblr-code/pansou-bot` | 从哪个 GitHub 仓库的 Releases 下载新后端 |
| `BACKEND_UPDATE_CHECK_HOURS` | `24` | 自动检查间隔，`0` 关闭（`/upgrade` 仍可手动用） |
| `BACKEND_AUTO_UPGRADE` | `false` | 发现新版本时直接升级 |
| `BACKEND_BUNDLED_DIR` | `/opt/pansou` | 镜像自带后端的位置，一般不用改 |

自己 fork 了本仓库、想用自己编译的后端，把 `BACKEND_UPDATE_REPO` 改成你的仓库即可：fork 里的 Backend release 工作流会照样每天发布。

## 不用 Docker

需要 Python 3.11 / 3.12、Go 1.25 和 git。先从上游源码编译后端，再运行机器人，机器人会自己启动这个后端：

```bash
git clone https://github.com/Tumblr-code/pansou-bot.git
cd pansou-bot
sh backend/build.sh --arch amd64 --out "$PWD/pansou-backend"     # ARM 机器用 arm64
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env     # 填 TG_BOT_TOKEN、ADMIN_IDS，并加上下面两行
```

```env
BACKEND_BUNDLED_DIR=/完整路径/pansou-bot/pansou-backend
DATA_DIR=./data
```

然后 `.venv/bin/python main.py`。在线升级同样可用。要开机自启，可以写一个 systemd 服务：`WorkingDirectory` 指向仓库目录，`ExecStart` 为 `.venv/bin/python main.py`，用一个专用的普通账号运行，并给它 `DATA_DIR` 的写权限。

## 排查

| 现象 | 看哪里 |
|---|---|
| `backend_missing` | 镜像里没有后端：自己构建时 Go 编译失败了，看构建输出 |
| `backend_port_in_use` | 8888 端口被占用。容器里不会发生；不用 Docker 时换一个 `BACKEND_PORT` |
| `backend_start_failed` | 后端没能在 `BACKEND_START_TIMEOUT` 内通过健康检查，看它前面的后端日志 |
| `backend_crash_loop_fallback` | 在线升级的版本反复崩溃，已经退回上一个版本 |
| `backend_update_check_failed` | 访问不了 GitHub，检查网络或 `HTTPS_PROXY` |
| 容器 unhealthy | 后端不健康。`/backend` 会显示原因，日志里有对应的 `backend_` 事件 |

## 发布是怎么来的

| 工作流 | 触发 | 产出 |
|---|---|---|
| CI | PR 和 main | Python 测试；构建镜像并在镜像里实际启动一次后端 |
| Image | main、`v*` 标签 | `ghcr.io/tumblr-code/pansou-bot` 镜像：`latest`、`sha-<提交号>`、版本号 |
| Backend release | 每天、手动 | `backend-<日期>-<提交号>` 发布：两个架构的压缩包、`SHA256SUMS`、构建来源证明 |

后端发布永远从上游 [fish2018/pansou](https://github.com/fish2018/pansou) 的源码编译，本仓库不修改后端代码。手动发布某个上游提交：在 Actions 里运行 Backend release，填入完整提交号。把镜像自带的版本更新到上游最新：`scripts/bump_backend.sh`，然后提交 PR。
