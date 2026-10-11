# TG PanSou Bot

[简体中文](README.md) · [Operations](docs/OPERATIONS.en.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md)

A Telegram bot that sends your keywords to a [PanSou](https://github.com/Tumblr-code/pansou) backend and returns cloud-drive resources grouped by storage provider.

- Search in private chats and groups; results are grouped by provider, paginated and refreshable
- Optional TMDB integration adds posters and summaries to film and TV searches
- Magnet links are delivered only to the person who searched; very long links arrive as a text file, never truncated
- Uses Telegram long polling, so no public IP, domain or HTTPS certificate is needed
- No HTTP API and no in-chat self-update command; logs mask tokens and omit search terms and user IDs by default

## Before you start

You need four things:

1. **A machine that can reach Telegram**, with Python 3.11 / 3.12 or Docker. If Telegram is not reachable directly, set a proxy in the configuration.
2. **A bot token.** Open [@BotFather](https://t.me/BotFather) in Telegram, send `/newbot` and follow the prompts. It returns a token that looks like `123456789:AA...`.
3. **Your own numeric Telegram ID**, to make yourself the administrator. Any "user ID" lookup bot will tell you.
4. **A running PanSou backend.** Follow the [PanSou tutorial](https://github.com/Tumblr-code/pansou/blob/main/README.en.md) on the same machine; the default address is `http://localhost:8888`.

## Five-minute start

```bash
git clone https://github.com/Tumblr-code/tg-pansou-bot.git
cd tg-pansou-bot
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Open `.env` in an editor and fill in at least these three values:

```env
TG_BOT_TOKEN=the token from BotFather
PANSOU_API_URL=http://localhost:8888
ADMIN_IDS=your numeric ID
```

Then start it:

```bash
.venv/bin/python main.py
```

Send `/start` to your bot in Telegram, then `/search keyword` to try a search. Press `Ctrl+C` to stop.

> One token can serve only one running instance. A second one fails with `Conflict` and neither receives messages.

## Run with Docker

```bash
git clone https://github.com/Tumblr-code/tg-pansou-bot.git
cd tg-pansou-bot
cp .env.example .env          # fill in the same three values
mkdir -p data && sudo chown 1000:1000 data && chmod 700 data
docker compose up -d --build
docker compose logs -f
```

The container runs as a non-root user with a read-only root filesystem and keeps user settings in `./data`. The example uses host networking and targets Linux: point the backend address at the host's `http://localhost:8888`.

To start it at boot, restart it on failure and run it under a dedicated system account, see the [operations guide](docs/OPERATIONS.en.md).

## Commands

| Command | Purpose | Who |
|---|---|---|
| `/search keyword` | Search for resources | Everyone |
| `/s keyword` | Search inside a group | Everyone |
| `/help` | Show help | Everyone |
| `/settings` | View or change search settings | Administrators |
| `/types` | List supported storage providers | Administrators |
| `/sources`, `/plugins`, `/channels` | Show sources, plugins and channels | Administrators |
| `/filter` | Manage keyword filters | Administrators |
| `/reset` | Reset search settings | Administrators |
| `/status` | Check the bot and the backend | Administrators |
| `/refresh` | Refresh the runtime cache | Administrators |

While `ADMIN_IDS` is empty, administrator commands are closed to everyone.

## Configuration

Everything is set in `.env`. [.env.example](.env.example) has the full annotated list.

| Variable | Default | Meaning |
|---|---|---|
| `TG_BOT_TOKEN` | none, required | The token from BotFather |
| `PANSOU_API_URL` | `http://localhost:8888` | Address of the PanSou backend |
| `PANSOU_API_TOKEN` | empty | Bearer token, when the backend has authentication enabled |
| `ADMIN_IDS` | empty | Comma-separated numeric administrator IDs |
| `DATA_DIR` | `./data` | Where user settings are stored |
| `HTTP_PROXY` / `HTTPS_PROXY` | empty | Outbound proxy for Telegram and the backend |
| `MAX_CONCURRENT_SEARCHES` / `SEARCH_QUEUE_TIMEOUT` | `4` / `8` s | Concurrent searches and the longest wait in the queue |
| `SEARCH_TIMEOUT` / `MAX_KEYWORD_LENGTH` | `30` s / `128` chars | Per-search timeout and keyword length limit |
| `TMDB_READ_ACCESS_TOKEN` / `TMDB_API_KEY` | empty | Optional; either one enables film and TV metadata |
| `DROP_PENDING_UPDATES` | `false` | Whether to discard messages queued while the bot was offline |
| `APP_VERSION` | `dev` | Version label shown by `/status` |

## Troubleshooting

- **`Conflict` / `getUpdates` at startup**: another instance is running with the same token. Stop it first.
- **Messages arrive but searches return nothing**: check the backend first; `curl http://localhost:8888/api/health` should return `"status":"ok"`. Then check `PANSOU_API_URL`, the proxy and the backend token.
- **Administrator commands do nothing**: `ADMIN_IDS` is empty or is not your own numeric ID.
- **No film or TV metadata**: TMDB credentials are missing or TMDB is unreachable. Plain resource search keeps working.
- **Settings cannot be saved**: check that `DATA_DIR` exists and is writable by the user running the bot.

The [operations guide](docs/OPERATIONS.en.md) covers further diagnosis, upgrades, rollback, backup and recovery.

## Security notes

- The token is the bot's password. Keep it out of Git, images, issues and chats; if it leaks, replace it at once with `/revoke` in BotFather.
- Make `.env` readable only by you: `chmod 600 .env`.
- The PanSou backend has no authentication by default. Keep it on the loopback address and never expose port 8888 to the internet.

## Development

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python scripts/verify_source_manifest.py
.venv/bin/python scripts/secret_scan.py
.venv/bin/ruff check .
.venv/bin/pytest -q
.venv/bin/python scripts/smoke_test.py
.venv/bin/python -m pip check
```

Every test uses mocked data and mocked network clients; none needs a real token or sends anything to Telegram. After changing `main.py`, `requirements.txt` or `src/`, run `scripts/verify_source_manifest.py --update` to refresh the [source manifest](docs/SOURCE_MANIFEST.json). `scripts/package_release.py --version vX.Y.Z` builds a release archive containing only source, templates and documentation.

## License

This repository does not currently declare a project license. The PanSou backend is MIT-licensed, which does not extend to this project. Dependencies keep their own licenses; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
