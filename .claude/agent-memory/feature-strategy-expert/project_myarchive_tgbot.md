---
name: myarchive_tgbot project context
description: Core architecture, tech stack, and key decisions for the myarchive Telegram bot project
type: project
---

Python 3.12 async Telegram bot (python-telegram-bot v21, aiomysql, MySQL via Docker).

**Why:** Personal archive tool for saving links and forwarded Telegram messages, with browse/search/delete and now scheduled reminders.

**Stack:**
- PTB v21 with job_queue (requires [job-queue] extras — without them job_queue is None and bot crashes on startup)
- aiomysql pool with init_command='SET time_zone = "+00:00"' to force UTC on all connections
- All datetime comparisons use naive UTC (datetime.now(timezone.utc).replace(tzinfo=None)); datetime.utcnow() is deprecated in 3.12
- pymysql (sync) used by migrate.py only — aiomysql is async-only and not usable in standalone CLI scripts

**Key patterns:**
- Stateless pagination: page/query encoded in callback_data strings (colon-delimited)
- No AI/LLM features — plain CRUD + Telegram API
- DB pool singleton in db/pool.py; init_pool() called once at startup via post_init hook

**Migration system (added 2026-05-06):**
- migrations/*.sql files (0001...) applied by migrate.py (standalone, synchronous, uses pymysql)
- schema_migrations table tracks applied migrations; bootstrap step creates it before querying
- init.sql kept for Docker first-run but now also includes schema_migrations table

**How to apply:** When touching datetime, DB connections, or job_queue — check these decisions are in place.
