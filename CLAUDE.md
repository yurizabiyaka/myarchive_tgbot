# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

**myarchive_tgbot** is an async Telegram bot (Python 3.12, python-telegram-bot v21, MySQL via aiomysql) that lets users save internet finds — links and forwarded Telegram messages — and later browse, search, and delete them.

## Running the bot

```bash
# 1. Start MySQL
docker-compose up -d

# 2. Copy and fill in secrets
cp .env.example .env
# edit .env: set BOT_TOKEN, DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the bot
python bot.py
```

The bot uses `run_polling()` — no webhook setup required for development.

## Environment variables

All secrets come from `.env` (loaded by `python-dotenv`). See `.env.example` for the full list. The `config.py` module reads them into a typed `Config` dataclass that every other module imports.

## Architecture

### Package layout

```
bot.py            # Entry point: builds Application, registers all handlers, calls run_polling()
config.py         # Config dataclass populated from environment variables
db/
  pool.py         # aiomysql pool singleton — init_pool() called at startup, get_pool() used everywhere
  users.py        # ensure_user(), delete_user()
  items.py        # save_item(), list_items(), search_items(), delete_item(), count_items(), count_search()
handlers/
  start.py        # /start
  help.py         # /help
  forgetme.py     # /forgetme (with inline confirmation button)
  save.py         # Ingests forwarded messages and URL-bearing messages
  browse.py       # /list, /find, and all inline-keyboard callback handlers
```

### How pagination works (important)

There is **no server-side session state**. The current page number and search query are encoded directly in each button's `callback_data` string, using a colon-delimited schema:

```
list:page:<N>
find:<query>:page:<N>
del:list:<item_id>:page:<N>
del:find:<query>:<item_id>:page:<N>
```

`CallbackQueryHandler` in `browse.py` parses these strings and either edits the existing message in place or deletes the item and re-renders. This means all navigation is stateless and concurrent-user-safe.

### Forwarded message vs. URL detection (in `handlers/save.py`)

PTB v21 uses `message.forward_origin` (not the deprecated `forward_from`/`forward_from_chat`). The handler uses `filters.FORWARDED` as the PTB filter. URL detection inspects `message.entities` for `MessageEntity.URL` and `MessageEntity.TEXT_LINK` types. Forwarded check runs first; URL check runs second.

### Database layer

`db/pool.py` holds a module-level pool created once at startup. All DB functions use `async with pool.acquire() as conn` / `async with conn.cursor() as cur`. The `items` table has a `FULLTEXT INDEX` on `(content, text)` enabling `MATCH ... AGAINST IN BOOLEAN MODE` for `/find`.

Foreign key `items.user_id → users.id ON DELETE CASCADE` means `/forgetme` only needs to delete the user row.

## Key constraints to keep in mind

- **No AI/LLM features** — this is plain CRUD + Telegram API.
- Handlers must not raise unhandled exceptions; wrap DB calls in try/except and reply with a user-friendly error message on failure.
- The `/find` query is embedded in callback_data; keep it bounded (truncate or hash if over ~50 chars) to stay within Telegram's 64-byte callback_data limit.
- `python-telegram-bot` v21 is fully async — never use blocking I/O inside handlers.
