---
name: myarchive_tgbot Infrastructure Setup
description: MySQL infrastructure files, docker-compose configuration, and database schema for myarchive_tgbot Telegram bot project
type: project
---

## Project: myarchive_tgbot — Infrastructure & Database Setup

### Core Infrastructure Files

**Location**: `/home/master/source/myarchive_tgbot/`

#### docker-compose.yml
- Service: MySQL 8.0
- Container name: `myarchive_mysql`
- Port: `3306:3306` (localhost to container)
- Named volume: `mysql_data` for persistence
- Init script: `./init.sql` auto-executes on first startup via docker-entrypoint
- Health check: mysqladmin ping with 10s intervals, 5 retries
- Network: Custom bridge `myarchive_network`
- Restart: `unless-stopped` for automatic recovery

Environment variables (from `.env`):
- `MYSQL_ROOT_PASSWORD`, `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD` (container config)
- Application connects using `MYSQL_USER`/`MYSQL_PASSWORD` (not root)

#### init.sql
Database schema:
1. **users table**: Telegram user metadata
   - `id` (BIGINT PRIMARY KEY) — Telegram user_id
   - `username`, `first_name`, `last_name` (VARCHAR 255)
   - `registered_at` (DATETIME DEFAULT CURRENT_TIMESTAMP)

2. **items table**: Saved links and forwarded messages
   - `id` (BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY)
   - `user_id` (BIGINT NOT NULL) — Foreign key to users.id with CASCADE delete
   - `type` (ENUM 'link', 'forwarded_message')
   - `content` (TEXT) — URL or forwarded message reference
   - `text` (TEXT, nullable) — message caption/text
   - `saved_at` (DATETIME DEFAULT CURRENT_TIMESTAMP)
   - FULLTEXT index on (content, text) for `/find` keyword search
   - InnoDB engine, utf8mb4 charset

#### .env.example
Template for environment configuration:
- `BOT_TOKEN` — Telegram bot token
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` — Application DB connection
- `MYSQL_ROOT_PASSWORD`, `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD` — Container initialization
- `DB_POOL_MIN`, `DB_POOL_MAX` — Connection pool settings for aiomysql

**User action**: Copy `.env.example` to `.env` and populate `BOT_TOKEN` before running bot

### Known Behaviors & Quirks

- Init script only executes on first container creation (when volume is empty)
- To reset schema: `docker-compose down -v` (removes volume), then `docker-compose up`
- Application connects as `MYSQL_USER` (not root) — least-privilege approach
- FULLTEXT index on InnoDB requires MySQL 5.7+ (satisfied by MySQL 8.0)

### Integration Points

- **Python Bot Application** (TBD): Coder will implement `config.py`, `db/`, `handlers/`, `bot.py`
- **Connection**: Uses aiomysql library with connection pool (min 1, max 5 by default)
- **Database queries**: `/find` uses `MATCH ... AGAINST` syntax; `/list` uses pagination

### Operational Notes

**Startup**: `docker-compose up -d` starts MySQL; health check passes within ~30 seconds
**Integration test**: `docker-compose up -d && python bot.py` (when bot code is ready)
**Cleanup**: `docker-compose down -v` removes containers and persistent data
**Logs**: `docker-compose logs mysql` for MySQL container diagnostics

### Files & Status

- ✅ docker-compose.yml (created 2026-05-05)
- ✅ init.sql (created 2026-05-05)
- ✅ .env.example (created 2026-05-05)
- 🔄 config.py (pending Coder)
- 🔄 db/*.py (pending Coder)
- 🔄 handlers/*.py (pending Coder)
- 🔄 bot.py (pending Coder)
- 🔄 requirements.txt (pending Coder)
