# PanSou Bot

[中文](README.md) · [Operations](docs/OPERATIONS.en.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md)

A Telegram bot that searches cloud-drive share links, **with the search backend built in**. One Docker container runs both the bot and the [PanSou](https://github.com/fish2018/pansou) search service, and the backend can be upgraded online with a single Telegram command.

- Search in private chats and groups; results are grouped by drive type, paginated and refreshable
- Built-in PanSou backend: the bot starts it, health-checks it and restarts it after a crash
- Online upgrades: a new backend is compiled from upstream source every day; admins send `/upgrade` to install it, with automatic recovery on failure and one-step rollback
- Optional TMDB integration adds posters and summaries to film and TV searches
- Magnet links go only to the person who searched; very long links are sent as a text file
- Connects to Telegram by long polling: no public IP, domain or HTTPS certificate needed

## Before you start

You need three things:

1. **A Linux machine that can reach Telegram**, with Docker and the Compose plugin, x86_64 or ARM64. If Telegram is blocked, set a proxy in the configuration.
2. **A bot token.** Talk to [@BotFather](https://t.me/BotFather), send `/newbot` and follow the prompts. You get a token like `123456789:AA...`.
3. **Your own numeric Telegram ID**, to make yourself an admin. Any "show my user ID" bot will tell you.

## Five-minute start

```bash
git clone https://github.com/Tumblr-code/pansou-bot.git
cd pansou-bot
cp .env.example .env
```

Open `.env` and fill in two values:

```env
TG_BOT_TOKEN=the token from BotFather
ADMIN_IDS=your numeric ID
```

Prepare the data directory (the container runs as UID 1000) and start:

```bash
mkdir -p data && sudo chown 1000:1000 data
docker compose pull
docker compose up -d
docker compose logs -f
```

`docker compose pull` fetches the prebuilt image (amd64 / arm64). To build from your checkout instead, skip it and run `docker compose up -d --build`; the first build compiles the backend and takes a few minutes.

When the log shows `backend_ready` and `telegram_api_connected`, both the backend and the bot are up. Send `/start` to your bot, then a keyword to try a search.

> A token can only be used by one running instance at a time. A second one fails with `Conflict`, and neither receives messages.

## Upgrading the backend online

PanSou changes often (data-source plugins come and go). This repository's GitHub Actions check upstream once a day; for every new commit they compile amd64 and arm64 builds from source and publish them with a SHA256 file under [Releases](https://github.com/Tumblr-code/pansou-bot/releases) (tags look like `backend-20261012-221665fb2c92`).

| Task | How |
|---|---|
| See the backend version and state | Send `/backend`; `/status` shows it too |
| Check and upgrade | Send `/upgrade` and tap "立即升级" (upgrade now) when a new build exists |
| Go back to the previous build | Send `/upgrade rollback` |
| Get told about new builds | Checked every 24 hours by default; all admins get a private message |
| Fully automatic upgrades | Set `BACKEND_AUTO_UPGRADE=true` in `.env` |

An upgrade downloads the build, verifies its SHA256, starts it, and only switches over once it passes the health check. If the new build does not come up, the old one keeps running and that build is remembered and not offered again. Downloaded builds live in `data/backend/`, so they survive container restarts and re-creation.

The bot itself (the Python code) is upgraded by updating the image: `docker compose pull && docker compose up -d`.

## Commands

| Command | Purpose | Who |
|---|---|---|
| `/search keyword` | Search (in a private chat, just send the keyword) | Everyone |
| `/s keyword` | Search in a group | Everyone |
| `/help` | Help | Everyone |
| `/settings` | Show or change search settings | Admins |
| `/types` | Supported drive types | Admins |
| `/sources`, `/plugins`, `/channels` | Sources, plugins and channels | Admins |
| `/filter` | Keyword filters | Admins |
| `/reset` | Reset search settings | Admins |
| `/status` | Bot and backend health | Admins |
| `/refresh` | Refresh runtime caches | Admins |
| `/backend` | Backend version, uptime and previous build | Admins |
| `/upgrade` | Upgrade the backend online; `/upgrade rollback` to roll back | Admins |

Without `ADMIN_IDS`, admin commands are closed to everyone.

## Configuration

Everything goes in `.env`; see [.env.example](.env.example) for the full list with comments. The common ones:

| Variable | Default | Meaning |
|---|---|---|
| `TG_BOT_TOKEN` | none, required | Token from BotFather |
| `ADMIN_IDS` | empty | Admin numeric IDs, comma-separated |
| `HTTP_PROXY` / `HTTPS_PROXY` | empty | Outbound proxy shared by the bot and the backend; never used for the local backend |
| `BACKEND_UPDATE_CHECK_HOURS` | `24` | How often to look for a new backend; `0` turns it off |
| `BACKEND_AUTO_UPGRADE` | `false` | Install new builds right away instead of only notifying |
| `CHANNELS` / `ENABLED_PLUGINS` | upstream's | Telegram channels and plugins the backend searches, comma-separated; empty means upstream's default lists |
| `TMDB_READ_ACCESS_TOKEN` / `TMDB_API_KEY` | empty | Optional; either one enables film and TV details |

PanSou's own settings (cache, concurrency, timeouts and so on, see the [upstream docs](https://github.com/fish2018/pansou#readme)) can go in the same `.env` and are passed to the backend. The bot token and TMDB credentials are never passed to the backend process.

To use an existing, separately deployed PanSou instead, set `PANSOU_BACKEND=external` and `PANSOU_API_URL`; the built-in backend then stays off.

## Troubleshooting

- **`Conflict` / `getUpdates` at start-up**: another instance is using the same token. Stop it first.
- **`PermissionError` in the log, or settings fail to save**: `data` is not owned by UID 1000. Run `sudo chown -R 1000:1000 data`.
- **Messages arrive but searches return nothing**: send `/backend` to check the backend; if it is down, look for log lines starting with `backend_` in `docker compose logs`.
- **`/upgrade` cannot reach GitHub**: the machine needs access to `api.github.com` and `github.com`; set `HTTPS_PROXY` in `.env` if necessary.
- **Admin commands do nothing**: `ADMIN_IDS` is empty or is not your own numeric ID.
- **No film or TV details**: TMDB credentials are missing or TMDB is unreachable. Ordinary searches still work.

More (installing without Docker, backup and restore, calling the search API directly) is in the [operations guide](docs/OPERATIONS.en.md).

## Security notes

- The token is the bot's password. Never commit it, bake it into an image, or paste it into issues or chats. If it leaks, `/revoke` it in BotFather at once.
- Make `.env` readable only by you: `chmod 600 .env`.
- The built-in backend is only reachable inside the container by default. If you really need the search API on the host, publish it on `127.0.0.1` only, never to the internet (the backend has no authentication by default).
- Online upgrades download only from the repository in `BACKEND_UPDATE_REPO` and verify SHA256; each release also carries a GitHub build provenance attestation you can check with `gh attestation verify`.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python scripts/secret_scan.py
.venv/bin/ruff check .
.venv/bin/pytest -q
.venv/bin/python scripts/smoke_test.py
```

All tests use mocked data: Telegram and GitHub are mocked and the backend is replaced by a fake executable, so no real token, Go or Docker is needed.

Layout:

```text
main.py, src/          the bot (Python); src/backend_*.py run and upgrade the built-in backend
backend/UPSTREAM       the upstream PanSou revision bundled in the image
backend/build.sh       compiles the backend from upstream source (used by the Dockerfile and the release workflow)
scripts/bump_backend.sh  moves the bundled revision to upstream's latest commit
```

## License

This repository has no project license declared yet. The bundled PanSou backend comes from [fish2018/pansou](https://github.com/fish2018/pansou) under the MIT license, and its LICENSE ships in the image and in every release archive; that does not license this project. Dependencies keep their own licenses, see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
