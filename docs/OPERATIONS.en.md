# PanSou Bot operations

[中文](OPERATIONS.zh-CN.md) · [Home](../README.en.md)

This guide covers running the bot long term: what is in the container, where data lives, how to upgrade and roll back, how to back up, and how to install without Docker. To just get it running, the [five-minute start](../README.en.md#five-minute-start) is enough.

## What runs in the container

```text
tini                     PID 1, forwards signals and reaps children
└─ python main.py        the bot
   └─ pansou             the PanSou backend, listening on port 8888 inside the container only
```

At start-up the bot launches the backend and waits for its health check (`/api/health`) before taking messages. If the backend exits unexpectedly it is restarted, with the delay growing from 1 to 30 seconds. If a build installed by an online upgrade crashes three times within two minutes, the bot falls back to the previous build.

The image's root filesystem is read-only; everything writable lives in the directory mounted at `/data`:

```text
data/
├─ user_settings.json        users' search settings
└─ backend/
   ├─ state.json             current backend build, previous build, builds that failed to start
   ├─ releases/<commit>/     builds downloaded by online upgrades (at most two kept)
   ├─ cache/                 the backend's search cache
   └─ work/                  the backend's working directory
```

The backend bundled with the image is in `/opt/pansou/`; its revision is recorded in `backend/UPSTREAM` in this repository. When `data/backend/state.json` is missing or points at an unusable build, the bundled build runs.

## Everyday tasks

```bash
docker compose logs -f --tail=100     # logs
docker compose restart                # restart
docker compose down                   # stop and remove the container (data is untouched)
docker compose ps                     # state; HEALTHY means the backend health check passes
```

Logs are JSON. The bot does not log search terms or user IDs by default and masks the token; backend logs are passed through as they are.

## Upgrading

**Backend**: send `/upgrade` in Telegram, see the [home page](../README.en.md#upgrading-the-backend-online). If you do not want online upgrades, set `BACKEND_UPDATE_CHECK_HOURS` to `0` and upgrade by updating the image.

**The bot and the bundled backend**:

```bash
docker compose pull
docker compose up -d
```

If you build yourself: `git pull && docker compose up -d --build`.

If an online upgrade installed a build newer than the one in the new image, the container keeps running the upgraded build after re-creation. To go back to the bundled build, send `/upgrade rollback` until `/backend` shows "镜像自带" (bundled), or stop the container and delete `data/backend/state.json`.

**Rolling back the image**: in `docker-compose.yml`, set `image:` to a `sha-<commit>` tag and run `docker compose up -d`. Available tags are on the repository's Packages page.

## Backup and restore

Only two things need backing up: `.env` and `data/user_settings.json`. Everything in `data/backend/` can be downloaded or regenerated.

```bash
tar -czf pansou-bot-backup-$(date +%F).tar.gz .env data/user_settings.json
```

To restore, stop the container, put both files back, make sure `data` belongs to UID 1000, and start again.

## Backend configuration

Variables in `.env` are passed to the backend as they are, except `TG_BOT_TOKEN`, `TMDB_READ_ACCESS_TOKEN` and `TMDB_API_KEY`. The bot sets `PORT` and `CACHE_PATH` itself.

When `CHANNELS`, `ENABLED_PLUGINS` and the like are empty, the defaults shipped with the running backend build apply (taken from upstream's Dockerfile and stored in each build's `defaults.env`). That way plugins added or removed upstream follow along when the backend is upgraded; values you set yourself always win.

## All backend settings

| Variable | Default | Meaning |
|---|---|---|
| `BACKEND_PORT` | `8888` | Port the backend listens on inside the container, used only by the bot |
| `BACKEND_START_TIMEOUT` | `60` | Seconds to wait for the backend health check |
| `BACKEND_UPDATE_REPO` | `Tumblr-code/pansou-bot` | GitHub repository whose Releases provide new backend builds |
| `BACKEND_UPDATE_CHECK_HOURS` | `24` | Automatic check interval; `0` turns it off (`/upgrade` still works) |
| `BACKEND_AUTO_UPGRADE` | `false` | Install new builds as soon as they are found |
| `BACKEND_BUNDLED_DIR` | `/opt/pansou` | Where the bundled backend lives; normally left alone |

If you fork this repository and want backends built by your fork, point `BACKEND_UPDATE_REPO` at it: the fork's Backend release workflow publishes daily in the same way.

## Without Docker

Needs Python 3.11 / 3.12, Go 1.25 and git. Compile the backend from upstream source first, then run the bot; the bot starts that backend itself:

```bash
git clone https://github.com/Tumblr-code/pansou-bot.git
cd pansou-bot
sh backend/build.sh --arch amd64 --out "$PWD/pansou-backend"     # arm64 on ARM machines
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env     # fill in TG_BOT_TOKEN and ADMIN_IDS, and add the two lines below
```

```env
BACKEND_BUNDLED_DIR=/full/path/to/pansou-bot/pansou-backend
DATA_DIR=./data
```

Then run `.venv/bin/python main.py`. Online upgrades work here too. To start at boot, write a systemd service with `WorkingDirectory` set to the checkout and `ExecStart` set to `.venv/bin/python main.py`, running as a dedicated unprivileged account that can write to `DATA_DIR`.

## Troubleshooting

| Symptom | Where to look |
|---|---|
| `backend_missing` | The image has no backend: when building yourself, the Go build failed; check the build output |
| `backend_port_in_use` | Port 8888 is taken. Cannot happen in the container; without Docker, pick another `BACKEND_PORT` |
| `backend_start_failed` | The backend did not pass its health check within `BACKEND_START_TIMEOUT`; read the backend log just before it |
| `backend_crash_loop_fallback` | An upgraded build kept crashing and the bot went back to the previous one |
| `backend_update_check_failed` | GitHub is unreachable; check the network or `HTTPS_PROXY` |
| Container unhealthy | The backend is unhealthy. `/backend` shows why, and the log has matching `backend_` events |

## Where releases come from

| Workflow | Trigger | Output |
|---|---|---|
| CI | PRs and main | Python tests; builds the image and starts the backend inside it once |
| Image | main, `v*` tags | `ghcr.io/tumblr-code/pansou-bot` image: `latest`, `sha-<commit>`, version tags |
| Backend release | daily, manual | `backend-<date>-<commit>` release: archives for both architectures, `SHA256SUMS`, build provenance |

Backend releases are always compiled from the source of upstream [fish2018/pansou](https://github.com/fish2018/pansou); this repository does not modify backend code. To publish a specific upstream commit, run Backend release from Actions with the full commit SHA. To move the bundled build to upstream's latest commit, run `scripts/bump_backend.sh` and open a PR.
