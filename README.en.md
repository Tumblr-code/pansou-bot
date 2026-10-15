# PanSou Bot

[中文](README.md) · [Operations](docs/OPERATIONS.en.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md)

A Telegram bot that searches cloud-drive share links. It combines the [PanSou](https://github.com/fish2018/pansou) search engine and a Telegram bot into one project: a single Docker image that works as soon as you add a token, with a search engine you can upgrade online from Telegram.

- Search in private chats and groups; results are grouped by drive type, paginated and refreshable
- One container is everything: no other service to deploy or maintain
- Online upgrades: a new search engine is compiled from upstream source every day; admins send `/upgrade` to install it, with automatic recovery on failure and one-step rollback
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

`docker compose pull` fetches the prebuilt image (amd64 / arm64). To build from your checkout instead, skip it and run `docker compose up -d --build`; the first build compiles the search engine and takes a few minutes.

When the log shows `engine_ready` and `telegram_api_connected`, everything is up. Send `/start` to your bot, then a keyword to try a search.

> A token can only be used by one running instance at a time. A second one fails with `Conflict`, and neither receives messages.

## Online upgrades

The PanSou search engine changes often (data sources come and go). This repository's GitHub Actions check upstream once a day; for every new commit they compile amd64 and arm64 builds from source and publish them with a SHA256 file under [Releases](https://github.com/Tumblr-code/pansou-bot/releases).

| Task | How |
|---|---|
| See the search engine version and state | Send `/status` |
| Check and upgrade | Send `/upgrade` and tap "立即升级" (upgrade now) when a new build exists |
| Go back to the previous build | Send `/upgrade rollback` |
| Get told about new builds | Checked every 24 hours by default; all admins get a private message |
| Fully automatic upgrades | Set `AUTO_UPGRADE=true` in `.env` |

An upgrade downloads the build, verifies its SHA256, starts it, and only switches over once it passes the health check. If the new build does not come up, the old one keeps running and that build is remembered and not offered again. Downloaded builds live in `data/engine/`, so they survive container restarts and re-creation.

The bot's own code is updated with the image: `docker compose pull && docker compose up -d`.

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
| `/status` | Health and search engine version | Admins |
| `/refresh` | Refresh runtime caches | Admins |
| `/upgrade` | Upgrade the search engine online; `/upgrade rollback` to roll back | Admins |

Without `ADMIN_IDS`, admin commands are closed to everyone.

## Configuration

Everything goes in `.env`; see [.env.example](.env.example) for the full list with comments. The common ones:

| Variable | Default | Meaning |
|---|---|---|
| `TG_BOT_TOKEN` | none, required | Token from BotFather |
| `ADMIN_IDS` | empty | Admin numeric IDs, comma-separated |
| `HTTP_PROXY` / `HTTPS_PROXY` | empty | Outbound proxy for Telegram, GitHub and the search sources |
| `UPGRADE_CHECK_HOURS` | `24` | How often to look for a new build; `0` turns it off |
| `AUTO_UPGRADE` | `false` | Install new builds right away instead of only notifying |
| `CHANNELS` / `ENABLED_PLUGINS` | upstream's | Telegram channels and plugins to search, comma-separated; empty means upstream's default lists |
| `TMDB_READ_ACCESS_TOKEN` / `TMDB_API_KEY` | empty | Optional; either one enables film and TV details |

PanSou's own settings (cache, concurrency, timeouts and so on, see the [upstream docs](https://github.com/fish2018/pansou#readme)) can go in the same `.env` and take effect. The bot token and TMDB credentials are used by the bot only and never handed to the search engine process.

## Troubleshooting

- **`Conflict` / `getUpdates` at start-up**: another instance is using the same token. Stop it first.
- **`PermissionError` in the log, or settings fail to save**: `data` is not owned by UID 1000. Run `sudo chown -R 1000:1000 data`.
- **Messages arrive but searches return nothing**: send `/status` to check the search engine; if it is down, look for log lines starting with `engine_` in `docker compose logs`.
- **`/upgrade` cannot reach GitHub**: the machine needs access to `api.github.com` and `github.com`; set `HTTPS_PROXY` in `.env` if necessary.
- **Admin commands do nothing**: `ADMIN_IDS` is empty or is not your own numeric ID.
- **No film or TV details**: TMDB credentials are missing or TMDB is unreachable. Ordinary searches still work.

More (backup and restore, running without Docker) is in the [operations guide](docs/OPERATIONS.en.md).

## Security notes

- The token is the bot's password. Never commit it, bake it into an image, or paste it into issues or chats. If it leaks, `/revoke` it in BotFather at once.
- Make `.env` readable only by you: `chmod 600 .env`.
- The container needs no published ports, and should have none.
- Online upgrades download only from the repository in `UPGRADE_REPO` and verify SHA256; each release also carries a GitHub build provenance attestation you can check with `gh attestation verify`.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python scripts/secret_scan.py
.venv/bin/ruff check .
.venv/bin/pytest -q
.venv/bin/python scripts/smoke_test.py
```

All tests use mocked data: Telegram and GitHub are mocked and the search engine is replaced by a fake executable, so no real token, Go or Docker is needed.

Layout:

```text
main.py, src/            Python code; src/engine_*.py run and upgrade the search engine
engine/UPSTREAM          the upstream PanSou revision the image uses
engine/build.sh          compiles the search engine from upstream source (used by the Dockerfile and the release workflow)
scripts/bump_engine.sh   moves the image's revision to upstream's latest commit
```

## License

This repository has no project license declared yet. The PanSou search engine comes from [fish2018/pansou](https://github.com/fish2018/pansou) under the MIT license, and its LICENSE ships in the image and in every release archive; that does not license this project. Dependencies keep their own licenses, see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
