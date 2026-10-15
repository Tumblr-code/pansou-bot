# PanSou Bot operations

[中文](OPERATIONS.zh-CN.md) · [Home](../README.en.md)

This guide covers running PanSou Bot long term: what is in the container, where data lives, how to upgrade and roll back, how to back up, and how to run without Docker. To just get it running, the [five-minute start](../README.en.md#five-minute-start) is enough.

## What runs in the container

```text
tini                     PID 1, forwards signals and reaps children
└─ python main.py        the bot
   └─ pansou             the PanSou search engine, used only inside the container
```

At start-up the search engine is launched first, and messages are taken once it passes its health check. If it exits unexpectedly it is restarted, with the delay growing from 1 to 30 seconds. If a build installed by an online upgrade crashes three times within two minutes, the previous build comes back automatically.

The image's root filesystem is read-only; everything writable lives in the directory mounted at `/data`:

```text
data/
├─ user_settings.json        users' search settings
└─ engine/
   ├─ state.json             current build, previous build, builds that failed to start
   ├─ releases/<commit>/     builds downloaded by online upgrades (at most two kept)
   ├─ cache/                 search cache
   └─ work/                  the search engine's working directory
```

The search engine bundled with the image is in `/opt/pansou/`; its revision is recorded in `engine/UPSTREAM` in this repository. When `data/engine/state.json` is missing or points at an unusable build, the bundled build runs.

## Everyday tasks

```bash
docker compose logs -f --tail=100     # logs
docker compose restart                # restart
docker compose down                   # stop and remove the container (data is untouched)
docker compose ps                     # state; HEALTHY means the health check passes
```

Logs are JSON. Search terms and user IDs are not logged by default and the token is masked; the search engine's own log lines are passed through as they are.

## Upgrading

**Search engine**: send `/upgrade` in Telegram, see the [home page](../README.en.md#online-upgrades). If you do not want online upgrades, set `UPGRADE_CHECK_HOURS` to `0` and upgrade by updating the image.

**The whole image**:

```bash
docker compose pull
docker compose up -d
```

If you build yourself: `git pull && docker compose up -d --build`.

If an online upgrade installed a search engine newer than the one in the new image, the container keeps running the upgraded build after re-creation. To go back to the bundled build, send `/upgrade rollback` until `/status` shows "镜像自带" (bundled), or stop the container and delete `data/engine/state.json`.

**Rolling back the image**: in `docker-compose.yml`, set `image:` to a `sha-<commit>` tag and run `docker compose up -d`. Available tags are on the repository's Packages page.

## Backup and restore

Only two things need backing up: `.env` and `data/user_settings.json`. Everything in `data/engine/` can be downloaded or regenerated.

```bash
tar -czf pansou-bot-backup-$(date +%F).tar.gz .env data/user_settings.json
```

To restore, stop the container, put both files back, make sure `data` belongs to UID 1000, and start again.

## Search configuration

Variables in `.env` are handed to PanSou as they are, except `TG_BOT_TOKEN`, `TMDB_READ_ACCESS_TOKEN` and `TMDB_API_KEY`. `PORT` and `CACHE_PATH` are set by the program itself.

When `CHANNELS`, `ENABLED_PLUGINS` and the like are empty, the defaults shipped with the running search engine build apply (taken from upstream's Dockerfile and stored in each build's `defaults.env`). That way data sources added or removed upstream follow along with online upgrades; values you set yourself always win.

## All run and upgrade settings

| Variable | Default | Meaning |
|---|---|---|
| `UPGRADE_CHECK_HOURS` | `24` | Automatic check interval; `0` turns it off (`/upgrade` still works) |
| `AUTO_UPGRADE` | `false` | Install new builds as soon as they are found |
| `UPGRADE_REPO` | `Tumblr-code/pansou-bot` | GitHub repository whose Releases provide new builds |
| `ENGINE_START_TIMEOUT` | `60` | Seconds to wait for the search engine health check |
| `ENGINE_PORT` | `8888` | Port the search engine listens on inside the container, used only by the bot |
| `ENGINE_DIR` | `/opt/pansou` | Where the bundled search engine lives; normally left alone |

If you fork this repository and want builds made by your fork, point `UPGRADE_REPO` at it: the fork's Engine release workflow publishes daily in the same way.

## Without Docker

Needs Python 3.11 / 3.12, Go 1.25 and git. Compile the search engine from upstream source first, then run the bot; it starts the search engine itself:

```bash
git clone https://github.com/Tumblr-code/pansou-bot.git
cd pansou-bot
sh engine/build.sh --arch amd64 --out "$PWD/pansou-engine"     # arm64 on ARM machines
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env     # fill in TG_BOT_TOKEN and ADMIN_IDS, and add the two lines below
```

```env
ENGINE_DIR=/full/path/to/pansou-bot/pansou-engine
DATA_DIR=./data
```

Then run `.venv/bin/python main.py`. Online upgrades work here too. To start at boot, write a systemd service with `WorkingDirectory` set to the checkout and `ExecStart` set to `.venv/bin/python main.py`, running as a dedicated unprivileged account that can write to `DATA_DIR`.

## Troubleshooting

| Symptom | Where to look |
|---|---|
| `engine_missing` | The image has no search engine: when building yourself, the Go build failed; check the build output |
| `engine_port_in_use` | Port 8888 is taken. Cannot happen in the container; without Docker, pick another `ENGINE_PORT` |
| `engine_start_failed` | The search engine did not pass its health check within `ENGINE_START_TIMEOUT`; read the log lines just before it |
| `engine_crash_loop_fallback` | An upgraded build kept crashing and the previous one came back |
| `engine_update_check_failed` | GitHub is unreachable; check the network or `HTTPS_PROXY` |
| Container unhealthy | The search engine is unhealthy. `/status` shows why, and the log has matching `engine_` events |

## Where releases come from

| Workflow | Trigger | Output |
|---|---|---|
| CI | PRs and main | Python tests; builds the image and starts the search engine inside it once |
| Image | main, `v*` tags | `ghcr.io/tumblr-code/pansou-bot` image: `latest`, `sha-<commit>`, version tags |
| Engine release | daily, manual | `engine-<date>-<commit>` release: archives for both architectures, `SHA256SUMS`, build provenance |

The search engine is always compiled from the source of upstream [fish2018/pansou](https://github.com/fish2018/pansou); this repository does not modify its code. To publish a specific upstream commit, run Engine release from Actions with the full commit SHA. To move the image's revision to upstream's latest commit, run `scripts/bump_engine.sh` and open a PR.
