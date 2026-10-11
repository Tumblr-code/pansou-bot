# TG PanSou Bot 安装与运维

[English](OPERATIONS.en.md) · [首页](../README.md)

这份教程讲怎样把机器人装成一个长期运行的系统服务：专用账号、开机自启、崩溃重启，以及之后的升级、回退和备份。只想先跑起来试试，看[首页的五分钟上手](../README.md#五分钟上手)就够了。

示例以 Ubuntu 24.04 + systemd 为准。尖括号里的内容换成你自己的值。

## 安装为系统服务

需要 Python 3.11 / 3.12（含 venv）、`ca-certificates`，以及一个已经能访问的 PanSou 后端。

```bash
git clone https://github.com/Tumblr-code/tg-pansou-bot.git
cd tg-pansou-bot
VERSION=$(git rev-parse --short HEAD)     # 用提交号给这次安装起个版本名

sudo useradd --system --home /nonexistent --shell /usr/sbin/nologin tgpansou
sudo install -d -m 0755 /opt/tg-pansou-bot/releases
sudo install -d -o tgpansou -g tgpansou -m 0700 /var/lib/tg-pansou-bot
sudo install -d -o root -g tgpansou -m 0750 /etc/tg-pansou-bot

git archive --format=tar --prefix="$VERSION/" HEAD | sudo tar -x -C /opt/tg-pansou-bot/releases
sudo python3 -m venv "/opt/tg-pansou-bot/releases/$VERSION/.venv"
sudo "/opt/tg-pansou-bot/releases/$VERSION/.venv/bin/pip" install -r "/opt/tg-pansou-bot/releases/$VERSION/requirements.txt"
sudo chown -R root:root "/opt/tg-pansou-bot/releases/$VERSION"
sudo chmod -R go-w "/opt/tg-pansou-bot/releases/$VERSION"

sudo install -o root -g tgpansou -m 0640 .env.example /etc/tg-pansou-bot/bot.env
sudoedit /etc/tg-pansou-bot/bot.env

sudo install -m 0644 deploy/systemd/tg-pansou-bot.service /etc/systemd/system/
sudo ln -s "/opt/tg-pansou-bot/releases/$VERSION" /opt/tg-pansou-bot/current
sudo systemctl daemon-reload
sudo systemctl enable --now tg-pansou-bot.service
```

装好之后的布局：

```text
/opt/tg-pansou-bot/releases/<版本>/   程序和它自己的虚拟环境，root 所有，服务账号不可写
/opt/tg-pansou-bot/current            指向当前版本的链接
/etc/tg-pansou-bot/bot.env            配置和 Token，0640 root:tgpansou
/var/lib/tg-pansou-bot/               用户设置，0700 tgpansou:tgpansou
```

在 `/etc/tg-pansou-bot/bot.env` 里至少填好：

```env
TG_BOT_TOKEN=<你的 Token>
PANSOU_API_URL=http://localhost:8888
ADMIN_IDS=<你的数字 ID>
DATA_DIR=/var/lib/tg-pansou-bot
APP_VERSION=<版本>
```

`DROP_PENDING_UPDATES` 保持 `false`。需要影视信息时再填一种 TMDB 凭据，两项都留空则不使用 TMDB。配置和 Token 只放在这个文件里，不要放进程序目录。

仓库里的 `deploy/systemd/pansou-native.service` 和端口保护脚本是给 PanSou 后端用的，安装方法见 [PanSou 的运维教程](https://github.com/Tumblr-code/pansou/blob/main/docs/OPERATIONS.zh-CN.md)。机器人的服务单元对后端是弱依赖：后端没装或暂时停止，机器人仍会启动，只是搜索会失败。

## Docker 方式

`docker-compose.yml` 使用 host 网络、非 root 用户、只读根文件系统和单独的 `/data`。先建好属于 uid/gid 1000、仅它可读写的 `./data`，在 `.env` 里填好配置，然后执行 `docker compose up -d --build`。host 网络的示例面向 Linux，后端地址写宿主机的 loopback。

systemd 和 Docker 两种方式不要用同一个 Token 同时运行。

## 验证

```bash
systemctl is-active tg-pansou-bot.service
systemctl show -p MainPID,NRestarts tg-pansou-bot.service
journalctl -u tg-pansou-bot.service -n 50 --no-pager
```

进程在运行、`NRestarts` 为 0 之后，在 Telegram 里实际走一遍：`/status`、一次搜索、切换分类、翻页。服务显示 active 不代表这些都正常。

把日志贴到 issue 之前先检查并隐去敏感内容。

## 故障排查

- **`Conflict` / `getUpdates`**：同一个 Token 有另一个实例在运行。先找到并停掉它，不要靠清空积压消息来解决。
- **后端不可用**：检查 PanSou 在本机的健康接口，以及地址、代理和认证配置。不要为了恢复搜索而关掉后端认证或把端口开放到公网。
- **设置无法写入**：检查 `DATA_DIR`、目录属主（0700）和服务单元里的可写路径。结构异常或损坏的设置文件会被隔离到一旁，先保留它再排查。
- **TMDB 不可用**：检查凭据和网络出口。影视信息获取失败时，资源搜索照常工作。

不需要真实 Token 的离线检查：`scripts/smoke_test.py` 和 `pytest`。

## 升级与回退

1. 获取新版本，放进一个新的 `releases/<版本>` 目录，建立它自己的虚拟环境并安装依赖，方法和首次安装相同。
2. 在新目录里运行离线检查。不要用正在使用的 Token 另起一个实例来测试。
3. 停止机器人，备份 `/var/lib/tg-pansou-bot`。
4. 切换并启动：

```bash
sudo ./scripts/activate_release.sh /opt/tg-pansou-bot/releases/<新版本>
```

脚本会把原来的 `current` 存为 `previous`，原子切换后启动并检查服务；启动失败时自动指回旧版本。启动成功后仍要按「验证」一节实际走一遍。

回退：

```bash
sudo ./scripts/activate_release.sh /opt/tg-pansou-bot/previous
```

回退前确认旧版本能读取现有的设置文件，不要用旧数据覆盖较新的用户设置。

## 备份与恢复

需要备份的内容：`/var/lib/tg-pansou-bot`（用户设置）、`/etc/tg-pansou-bot`（配置和 Token）、服务单元文件，以及 `current` 指向的版本。

- 备份前先停止机器人。
- 备份目录设为 0700、文件 0600，记录校验和，加密后存到另一台机器。
- 备份里有 Token 和用户设置，不要上传到 GitHub 或任何公开位置。

恢复演练在隔离目录里用假 Token 进行，不要启动真实的 polling：恢复后检查 JSON 结构、属主，再跑离线 smoke 和测试。正式恢复时先停掉唯一在运行的实例，恢复匹配的版本和数据后再验证；被隔离的异常文件先留着，不要用旧数据盲目覆盖较新的数据。

## 发布说明

目前没有发行版，请按本教程从源码安装。main 分支和 PR 只运行 CI；以后若有正式的 GitHub Release，会附上源码包、`PROVENANCE.json` 和 `SHA256SUMS`，下载后先运行 `sha256sum -c SHA256SUMS` 校验。发布只上传文件，不会替任何人部署或重启服务。
