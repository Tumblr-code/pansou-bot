# TG PanSou Bot installation and operations

[简体中文](OPERATIONS.zh-CN.md) · [Home](../README.en.md)

This guide installs the bot as a long-running system service with a dedicated account, start at boot and restart on failure, and then covers upgrades, rollback and backups. To just try it out, the [five-minute start](../README.en.md#five-minute-start) is enough.

Examples target Ubuntu 24.04 with systemd. Replace anything in angle brackets with your own value.

## Install as a system service

You need Python 3.11 / 3.12 with venv, `ca-certificates`, and a PanSou backend that is already reachable.

```bash
git clone https://github.com/Tumblr-code/tg-pansou-bot.git
cd tg-pansou-bot
VERSION=$(git rev-parse --short HEAD)     # or a release version such as v1.0.0

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

The resulting layout:

```text
/opt/tg-pansou-bot/releases/<version>/   program and its own virtual environment, owned by root, not writable by the service account
/opt/tg-pansou-bot/current               link to the active version
/etc/tg-pansou-bot/bot.env               configuration and token, 0640 root:tgpansou
/var/lib/tg-pansou-bot/                  user settings, 0700 tgpansou:tgpansou
```

Set at least these in `/etc/tg-pansou-bot/bot.env`:

```env
TG_BOT_TOKEN=<your token>
PANSOU_API_URL=http://localhost:8888
ADMIN_IDS=<your numeric ID>
DATA_DIR=/var/lib/tg-pansou-bot
APP_VERSION=<version>
```

Keep `DROP_PENDING_UPDATES=false`. Add one TMDB credential only if you want film and TV metadata; with both empty TMDB is not used. Configuration and the token live in this file only, never in the program directory.

`deploy/systemd/pansou-native.service` and the port guard script in this repository are for the PanSou backend; the [PanSou operations guide](https://github.com/Tumblr-code/pansou/blob/main/docs/OPERATIONS.en.md) explains how to install them. The bot's unit depends on the backend only weakly: the bot still starts when the backend is absent or stopped, and searches fail until it returns.

## Docker

`docker-compose.yml` uses host networking, a non-root user, a read-only root filesystem and a separate `/data`. Create `./data` owned by uid/gid 1000 and readable only by it, fill in `.env`, then run `docker compose up -d --build`. The host-network example targets Linux; point the backend address at the host loopback.

Do not run the systemd and Docker variants at the same time with one token.

## Verify

```bash
systemctl is-active tg-pansou-bot.service
systemctl show -p MainPID,NRestarts tg-pansou-bot.service
journalctl -u tg-pansou-bot.service -n 50 --no-pager
```

Once the process is running with `NRestarts` at 0, exercise it in Telegram: `/status`, one search, a category switch, a page turn. An active unit does not prove those work.

Review and redact logs before posting them in an issue.

## Troubleshooting

- **`Conflict` / `getUpdates`**: another instance is polling with the same token. Find and stop it; do not clear pending updates as a workaround.
- **Backend unavailable**: check the PanSou health endpoint on the same host, then the address, proxy and authentication settings. Do not disable backend authentication or open its port to the internet to get searches back.
- **Settings cannot be written**: check `DATA_DIR`, its ownership (0700) and the writable paths in the unit. A malformed or damaged settings file is set aside; keep it while you investigate.
- **TMDB unavailable**: check the credential and outbound access. Resource search keeps working when metadata fails.

Offline checks that need no real token: `scripts/smoke_test.py` and `pytest`.

## Upgrade and rollback

1. Get the new version into a new `releases/<version>` directory with its own virtual environment and dependencies, exactly as in the first install.
2. Run the offline checks there. Do not start a second instance with the token that is in use.
3. Stop the bot and back up `/var/lib/tg-pansou-bot`.
4. Switch and start:

```bash
sudo ./scripts/activate_release.sh /opt/tg-pansou-bot/releases/<new version>
```

The script saves the old `current` as `previous`, switches atomically, starts the service and checks it; if startup fails it points back to the old version. After a successful start, still walk through the Verify section.

To roll back:

```bash
sudo ./scripts/activate_release.sh /opt/tg-pansou-bot/previous
```

Before rolling back, confirm the older version can read the current settings files, and never overwrite newer user settings with older data.

## Backup and recovery

Back up `/var/lib/tg-pansou-bot` (user settings), `/etc/tg-pansou-bot` (configuration and token), the unit file, and the version `current` points to.

- Stop the bot before taking a backup.
- Use a 0700 directory and 0600 files, record checksums, encrypt, and store the result on another machine.
- A backup contains the token and user settings. Never upload it to GitHub or any public place.

Rehearse recovery in an isolated directory with a placeholder token and without starting real polling: check the JSON structure and ownership, then run the offline smoke test and the test suite. For a real recovery, stop the only running instance, restore a matching version and data, then verify. Keep any files that were set aside, and do not blindly overwrite newer data with older data.

## Releases

The main branch and pull requests only run CI. A final GitHub Release carries the source archive, `PROVENANCE.json` and `SHA256SUMS`; run `sha256sum -c SHA256SUMS` after downloading. Publishing uploads files only: it never deploys or restarts anything for anyone.
