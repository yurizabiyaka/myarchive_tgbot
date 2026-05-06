# TASK: Schedule Feature Fixes + DB Migration System

## Status
- [x] Strategy (Expert)
- [x] Detailed Planning (Planner) — skipped, scope precise from reviewer findings
- [x] Implementation (Coder)
- [ ] Testing (Tester)
- [ ] Review (Reviewer)
- [x] Deployment (DevOps)

## Feature Overview
The `/schedule` reminder feature was implemented (ClickUp task `86ahajvu1`). A code review
returned RED with 6 critical blockers (B1–B6) and 4 warnings (W1–W4) that must be fixed
before the feature is considered done. In parallel, the DevOps agent must build a repeatable
DB migration system for the project.

## Scope
### In Scope
- Fix all B1–B6 critical blockers
- Fix all W1–W4 warnings
- Build migrations/ directory with runner and three initial migration files
- Update init.sql to include schema_migrations table

### Out of Scope
- New features beyond the schedule command
- UI/UX changes to other handlers
- CI/CD pipeline changes

---

## CODER AGENT: All fixes required

### Files to modify
- `/home/master/source/myarchive_tgbot/requirements.txt`
- `/home/master/source/myarchive_tgbot/db/schedules.py`
- `/home/master/source/myarchive_tgbot/db/pool.py`
- `/home/master/source/myarchive_tgbot/handlers/schedule.py`
- `/home/master/source/myarchive_tgbot/reminder.py`
- `/home/master/source/myarchive_tgbot/bot.py`

---

### B1 — Add `[job-queue]` PTB extras (CRITICAL)

File: `requirements.txt`

Change:
```
python-telegram-bot==21.*
```
To:
```
python-telegram-bot[job-queue]==21.*
```

Without this the bot will start but `application.job_queue` will be `None` and line 40
of `bot.py` will raise `AttributeError`.

---

### B3 — Pin `timelength` to a specific version (CRITICAL)

File: `requirements.txt`

The code at `handlers/schedule.py` lines 27–31 already has defensive v1.x/v2.x branching,
which means the library API is unstable. Look up the latest stable version on PyPI and pin
it. As of 2026-05-06, pin to `timelength==2.0.3` (verify this is the latest stable).

Change:
```
timelength
```
To (example — verify the exact latest stable version):
```
timelength==2.0.3
```

---

### B2 — Timezone mismatch: UTC everywhere (CRITICAL)

**Problem**: `datetime.utcnow()` is deprecated in Python 3.12 and produces naive UTC datetimes.
MySQL `NOW()` returns the server local time (which may not be UTC inside Docker). This causes
reminders to fire hours late or early.

**Fix A — Force UTC on the aiomysql pool** (preferred, fixes the DB side globally):

File: `db/pool.py`, function `init_pool`, the `aiomysql.create_pool()` call.

Add `init_command='SET time_zone = "+00:00"'` to the pool creation parameters. This forces
every connection to use UTC, so MySQL `NOW()`, `UTC_TIMESTAMP()`, and `CURRENT_TIMESTAMP`
all return the same value and match our Python UTC datetimes.

Current call at lines 14–23:
```python
_pool = await aiomysql.create_pool(
    host=cfg.db_host,
    port=cfg.db_port,
    user=cfg.db_user,
    password=cfg.db_password,
    db=cfg.db_name,
    minsize=cfg.db_pool_min,
    maxsize=cfg.db_pool_max,
)
```

Replace with:
```python
_pool = await aiomysql.create_pool(
    host=cfg.db_host,
    port=cfg.db_port,
    user=cfg.db_user,
    password=cfg.db_password,
    db=cfg.db_name,
    minsize=cfg.db_pool_min,
    maxsize=cfg.db_pool_max,
    init_command='SET time_zone = "+00:00"',
)
```

**Fix B — Replace `datetime.utcnow()` calls with non-deprecated equivalent**:

Every occurrence of `datetime.utcnow()` must be replaced with:
```python
datetime.now(timezone.utc).replace(tzinfo=None)
```

This produces the same naive UTC datetime but uses the non-deprecated Python 3.12 API.

Files and lines with `datetime.utcnow()`:
- `handlers/schedule.py` line 122: `now = datetime.utcnow()`
- `handlers/schedule.py` line 169: `now = datetime.utcnow()`
- `reminder.py` line 37: `datetime.utcnow() + timedelta(...)`
- `reminder.py` line 46: `datetime.utcnow() + timedelta(...)`
- `reminder.py` line 64: `datetime.utcnow() + timedelta(...)`

In each file, add `timezone` to the datetime import:
- `handlers/schedule.py` line 2: change `from datetime import datetime, timedelta` to
  `from datetime import datetime, timedelta, timezone`
- `reminder.py` line 2: change `from datetime import datetime, timedelta` to
  `from datetime import datetime, timedelta, timezone`

---

### B4 — Race condition: atomic DB claim before sending (CRITICAL)

**Problem**: `run_repeating(interval=60)` can produce overlapping ticks. Two concurrent ticks
both call `get_due_schedules()` at the same time, get the same rows, and send duplicate
reminders to the user.

**Fix**: Use an atomic UPDATE to claim a schedule before processing it. This replaces the
SELECT-then-UPDATE pattern with an UPDATE-first approach.

**Step 1** — Add new function to `db/schedules.py`:

```python
async def claim_and_advance_schedule(
    pool: aiomysql.Pool,
    user_id: int,
    expected_next: datetime,
    interval_seconds: int,
) -> bool:
    """Atomically advance next_reminder_at to prevent duplicate sends.

    Uses an UPDATE with WHERE clause matching the current next_reminder_at value.
    Returns True if the row was updated (this process claimed it), False if
    another process already claimed it (rowcount == 0).

    Args:
        pool: Database connection pool.
        user_id: Telegram user ID.
        expected_next: The next_reminder_at value we read (optimistic lock key).
        interval_seconds: Reminder interval; used to compute the new next time.

    Returns:
        True if claim succeeded, False if already claimed by another tick.
    """
    from datetime import datetime, timedelta, timezone
    new_next = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=interval_seconds)
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE schedules
                SET next_reminder_at = %s
                WHERE user_id = %s AND next_reminder_at = %s
                """,
                (new_next, user_id, expected_next),
            )
            await conn.commit()
            return cur.rowcount > 0
```

**Step 2** — Update `get_due_schedules()` in `db/schedules.py` to also return `next_reminder_at`
so `reminder.py` has the value to pass as `expected_next`:

Change the SELECT in `get_due_schedules()` from:
```sql
SELECT user_id, interval_seconds, items_count
FROM schedules
WHERE next_reminder_at <= NOW()
```
To:
```sql
SELECT user_id, interval_seconds, items_count, next_reminder_at
FROM schedules
WHERE next_reminder_at <= NOW()
```

**Step 3** — Rewrite the per-schedule block in `reminder.py` `send_reminders()`:

The new flow must be:
1. For each due schedule from `get_due_schedules()`, call `claim_and_advance_schedule()`.
2. If it returns False, skip this schedule (another tick already claimed it).
3. Only then fetch items and send the message.
4. On transient send failure (anything EXCEPT `Forbidden` / `ChatMigrated`): log the error.
   The next_reminder_at has already been advanced, so the user will get the next reminder
   at the normal interval. This is acceptable — it avoids infinite retry loops.
5. On permanent failure (`Forbidden` = bot blocked, `ChatMigrated`): log and skip (no retry).

The rewritten `send_reminders` loop body (inside the `for schedule in due_schedules:` loop):

```python
from telegram.error import Forbidden, ChatMigrated

user_id = schedule["user_id"]
interval_seconds = schedule["interval_seconds"]
items_count = schedule["items_count"]
expected_next = schedule["next_reminder_at"]

try:
    # Atomically claim this schedule tick — prevents duplicate sends
    claimed = await claim_and_advance_schedule(
        pool, user_id, expected_next, interval_seconds
    )
    if not claimed:
        logger.info(f"Schedule for user {user_id} already claimed by another tick, skipping.")
        continue

    total_items = await count_items(pool, user_id)
    if total_items == 0:
        continue

    items = await get_random_items(pool, user_id, items_count)
    if not items:
        continue

    reminder_text = _format_reminder_message(items)
    # split if over Telegram limit
    MAX_LEN = 4096
    messages = _split_message(reminder_text, MAX_LEN)
    for msg in messages:
        await context.bot.send_message(chat_id=user_id, text=msg)

except (Forbidden, ChatMigrated) as e:
    logger.warning(f"Permanent send failure for user {user_id}: {e}. Schedule remains advanced.")
except Exception as e:
    logger.error(f"Error processing reminder for user {user_id}: {e}")
```

Import updates needed in `reminder.py`:
- Add `from telegram.error import Forbidden, ChatMigrated`
- Add `claim_and_advance_schedule` to the import from `db.schedules`
- Remove `update_next_reminder` from imports (no longer called directly in reminder.py)

---

### B5 — next_reminder_at advances even on transient failure (CRITICAL)

This is resolved by the B4 fix above. By advancing BEFORE sending (atomic claim), transient
failures still advance the schedule — which is acceptable because infinite retry loops are
worse than a missed tick. Permanent failures (Forbidden/ChatMigrated) are caught separately.
No additional changes needed beyond B4.

---

### B6 — `_parse_schedule_args` aborts on first unrecognized fragment (CRITICAL)

File: `handlers/schedule.py`, function `_parse_schedule_args`, lines 62–73.

Current problem: line 73 `return (None, None)` fires on the FIRST unrecognized fragment,
discarding any valid parts already parsed.

Fix: only return `(None, None)` after the loop if NOTHING was parsed (both remain None).
Unrecognized fragments should be silently skipped (or logged).

Replace lines 62–73:
```python
    for part in parts:
        items_match = re.match(r"^(\d+)\s+items?$", part, re.IGNORECASE)
        if items_match:
            items_count = int(items_match.group(1))
            continue

        seconds = _timelength_to_seconds(part)
        if seconds and seconds > 0:
            interval_seconds = seconds
            continue

        return (None, None)

    return (interval_seconds, items_count)
```

With:
```python
    for part in parts:
        items_match = re.match(r"^(\d+)\s+items?$", part, re.IGNORECASE)
        if items_match:
            items_count = int(items_match.group(1))
            continue

        seconds = _timelength_to_seconds(part)
        if seconds and seconds > 0:
            interval_seconds = seconds
            continue

        # Unrecognized fragment — skip it, do not abort

    if interval_seconds is None and items_count is None:
        return (None, None)

    return (interval_seconds, items_count)
```

---

### W1 — Enforce minimum interval of 5 minutes (300 seconds) (WARNING)

File: `handlers/schedule.py`, the `schedule_command` function.

After `interval_seconds, items_count = _parse_schedule_args(args_str)` is resolved and
before calling `upsert_schedule`, add a minimum check. Insert after line 167
(`items_count = max(1, min(items_count, 20))`):

```python
        MIN_INTERVAL = 300  # 5 minutes minimum
        if interval_seconds < MIN_INTERVAL:
            await update.message.reply_text(
                f"Minimum reminder interval is 5 minutes. "
                f"Please use an interval of at least 5 minutes."
            )
            return
```

Note: `interval_seconds` is guaranteed non-None at this point because the earlier guard
already returned if both were None AND the "no existing interval" check already returned.

---

### W2 — Message truncation/split for Telegram 4096-char limit (WARNING)

File: `reminder.py`

Add a helper function `_split_message` to split long messages at newline boundaries:

```python
def _split_message(text: str, max_len: int = 4096) -> list[str]:
    """Split text into chunks of at most max_len characters, splitting on newlines."""
    if len(text) <= max_len:
        return [text]
    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks
```

The B4 fix already calls `_split_message` in the send loop. Make sure this function is
defined in `reminder.py` (before or after `_format_reminder_message`).

---

### W3 — Cadence drift: anchor next time to prev_next + interval (WARNING)

File: `db/schedules.py`, new function `claim_and_advance_schedule` (added in B4).

In that function, instead of:
```python
new_next = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=interval_seconds)
```

Use:
```python
new_next = max(
    datetime.now(timezone.utc).replace(tzinfo=None),
    expected_next + timedelta(seconds=interval_seconds),
)
```

This anchors the next fire time to `prev_next + interval`, preventing drift. The `max()`
ensures we never schedule in the past if we're very late.

---

### W4 — Deduplicate content/text in reminder message (WARNING)

File: `reminder.py`, function `_format_reminder_message`, lines 106–108.

Current:
```python
        if text:
            text_snippet = text[:200] + "..." if len(text) > 200 else text
            lines.append(text_snippet)
```

Replace with:
```python
        if text and text != content:
            text_snippet = text[:200] + "..." if len(text) > 200 else text
            lines.append(text_snippet)
```

---

### Summary of all import changes

**`handlers/schedule.py` line 2**:
```python
from datetime import datetime, timedelta
```
→
```python
from datetime import datetime, timedelta, timezone
```

**`reminder.py` lines 1–11** — final imports block should be:
```python
import logging
from datetime import datetime, timedelta, timezone

from telegram.error import Forbidden, ChatMigrated
from telegram.ext import ContextTypes

from db.pool import get_pool
from db.schedules import (
    claim_and_advance_schedule,
    get_due_schedules,
    get_random_items,
)
from db.items import count_items
```

(Remove `update_next_reminder` import — it is no longer called from `reminder.py`.)

---

## DEVOPS AGENT: DB Migration System

### Overview

Build a migration runner and initial migration files. The system must:
1. Track applied migrations in a `schema_migrations` table
2. Apply missing migrations in order on startup or via explicit invocation
3. Be idempotent — running twice is safe

### Files to create

#### `migrations/0001_initial_schema.sql`

Content — the users and items tables from current `init.sql`:

```sql
-- Migration 0001: Initial schema — users and items tables
CREATE TABLE IF NOT EXISTS users (
    id            BIGINT PRIMARY KEY,
    username      VARCHAR(255),
    first_name    VARCHAR(255),
    last_name     VARCHAR(255),
    registered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS items (
    id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id     BIGINT NOT NULL,
    type        ENUM('link','forwarded_message') NOT NULL,
    content     TEXT NOT NULL,
    text        TEXT,
    saved_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FULLTEXT INDEX ft_items (content, text)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### `migrations/0002_add_schedules_table.sql`

```sql
-- Migration 0002: Add schedules table for /schedule reminder feature
CREATE TABLE IF NOT EXISTS schedules (
    user_id          BIGINT PRIMARY KEY,
    interval_seconds INT UNSIGNED NOT NULL,
    items_count      INT UNSIGNED NOT NULL DEFAULT 5,
    next_reminder_at DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

#### `migrations/0003_add_schema_migrations_table.sql`

```sql
-- Migration 0003: Add schema_migrations tracking table
-- NOTE: This migration is self-referential. The runner must create schema_migrations
-- BEFORE attempting to apply any migrations, then check which are already applied.
CREATE TABLE IF NOT EXISTS schema_migrations (
    id         VARCHAR(64) PRIMARY KEY,
    applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

#### `migrate.py`

A Python migration runner that:
- Loads `.env` from the project root (same as the bot)
- Connects to MySQL using the same env vars (DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD)
- Creates `schema_migrations` table if it doesn't exist (bootstrap step)
- Reads all `.sql` files from the `migrations/` directory, sorted by filename
- Queries `schema_migrations` for already-applied migration IDs
- For each pending migration, executes the SQL and records it in `schema_migrations`
- Exits with code 0 on success, non-zero on any failure
- Prints a clear log of what was applied and what was skipped

The runner must be synchronous (uses `pymysql` or `mysql-connector-python`, NOT aiomysql,
since it runs standalone outside the async bot context). Add the chosen sync MySQL driver
to `requirements.txt` as a separate entry with a pinned version.

Suggested implementation outline:

```python
#!/usr/bin/env python3
"""Database migration runner for myarchive_tgbot."""
import os
import sys
from pathlib import Path
import pymysql
from dotenv import load_dotenv

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

def get_connection():
    load_dotenv()
    return pymysql.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", 3306)),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        autocommit=False,
    )

def bootstrap_migrations_table(conn):
    """Ensure schema_migrations table exists before we try to query it."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id         VARCHAR(64) PRIMARY KEY,
                applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
    conn.commit()

def get_applied(conn) -> set:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM schema_migrations")
        return {row[0] for row in cur.fetchall()}

def apply_migration(conn, migration_id: str, sql: str):
    with conn.cursor() as cur:
        for statement in sql.split(";"):
            stmt = statement.strip()
            if stmt:
                cur.execute(stmt)
        cur.execute(
            "INSERT INTO schema_migrations (id) VALUES (%s)",
            (migration_id,),
        )
    conn.commit()

def main():
    conn = get_connection()
    try:
        bootstrap_migrations_table(conn)
        applied = get_applied(conn)
        migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        if not migration_files:
            print("No migration files found.")
            return
        for path in migration_files:
            migration_id = path.stem  # e.g. "0001_initial_schema"
            if migration_id in applied:
                print(f"[skip] {migration_id} already applied")
                continue
            print(f"[apply] {migration_id} ...")
            sql = path.read_text()
            apply_migration(conn, migration_id, sql)
            print(f"[done]  {migration_id}")
    except Exception as e:
        print(f"Migration failed: {e}", file=sys.stderr)
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
```

Add `pymysql==1.*` to `requirements.txt`.

#### Update `init.sql`

Add the `schema_migrations` table at the bottom of the existing `init.sql`, so Docker
first-run containers also get the tracking table:

```sql
-- schema_migrations table: tracks applied DB migrations
CREATE TABLE IF NOT EXISTS schema_migrations (
    id         VARCHAR(64) PRIMARY KEY,
    applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

---

## Done Criteria (DoD)

All of the following must pass before the task is marked complete:

1. **B1**: `requirements.txt` contains `python-telegram-bot[job-queue]==21.*`
2. **B2**: No `datetime.utcnow()` calls remain anywhere in the codebase; all replaced with `datetime.now(timezone.utc).replace(tzinfo=None)`; `db/pool.py` `init_pool` passes `init_command='SET time_zone = "+00:00"'` to `aiomysql.create_pool()`
3. **B3**: `timelength` is pinned to a specific version in `requirements.txt`
4. **B4**: `db/schedules.py` has `claim_and_advance_schedule()` function; `get_due_schedules()` returns `next_reminder_at`; `reminder.py` calls `claim_and_advance_schedule()` before fetching items
5. **B5**: `reminder.py` catches `Forbidden` and `ChatMigrated` separately from generic exceptions
6. **B6**: `_parse_schedule_args()` only returns `(None, None)` when NEITHER interval NOR items were parsed, not on first unrecognized fragment
7. **W1**: `schedule_command` enforces minimum 300-second interval with a user-friendly error
8. **W2**: `reminder.py` has `_split_message()` helper and sends multiple messages when content exceeds 4096 chars
9. **W3**: `claim_and_advance_schedule()` uses `max(now, expected_next + interval)` for new_next
10. **W4**: `_format_reminder_message()` skips appending `text` when `text == content`
11. **DevOps**: `migrations/` directory exists with `0001_initial_schema.sql`, `0002_add_schedules_table.sql`, `0003_add_schema_migrations_table.sql`
12. **DevOps**: `migrate.py` exists at project root and implements the full runner logic
13. **DevOps**: `init.sql` includes the `schema_migrations` table definition
14. **DevOps**: `pymysql` is added to `requirements.txt` with a pinned version
15. No Python syntax errors in any modified file
16. No unhandled exceptions in the modified code paths

---

## Agent Reports

### Coder Report

Completed 2026-05-06. All B1-B6 critical blockers and W1-W4 warnings implemented.

**Files modified:**
- `requirements.txt`: B1 (added [job-queue] extras), B3 (pinned timelength==2.0.3), added pymysql==1.*
- `db/pool.py`: B2 (added init_command for UTC timezone on all connections)
- `handlers/schedule.py`: B2 (replaced datetime.utcnow() x2, added timezone import), B6 (fixed _parse_schedule_args to skip unrecognized fragments instead of aborting), W1 (MIN_INTERVAL=300 guard)
- `db/schedules.py`: B4 (get_due_schedules now returns next_reminder_at; new claim_and_advance_schedule() function with optimistic locking and W3 cadence-anchor logic)
- `reminder.py`: Full rewrite — B4 (atomic claim before send), B5 (Forbidden/ChatMigrated caught separately), B2 (datetime.utcnow() replaced, timezone import), W2 (_split_message helper), W4 (text != content dedup guard)

**DoD verification:**
- B1: python-telegram-bot[job-queue]==21.* in requirements.txt — PASS
- B2: No datetime.utcnow() anywhere; init_command UTC on pool — PASS
- B3: timelength==2.0.3 pinned — PASS
- B4: claim_and_advance_schedule() in db/schedules.py; get_due_schedules returns next_reminder_at; reminder.py claims before fetching — PASS
- B5: Forbidden and ChatMigrated caught separately in reminder.py — PASS
- B6: _parse_schedule_args skips unrecognized fragments, only returns (None,None) if nothing parsed — PASS
- W1: MIN_INTERVAL=300 enforced in schedule_command — PASS
- W2: _split_message() in reminder.py, called before send_message — PASS
- W3: new_next = max(now, expected_next + interval) in claim_and_advance_schedule — PASS
- W4: `if text and text != content` guard in _format_reminder_message — PASS

### DevOps Report

Completed 2026-05-06. Migration system built.

**Files created:**
- `migrations/0001_initial_schema.sql`: users + items tables
- `migrations/0002_add_schedules_table.sql`: schedules table
- `migrations/0003_add_schema_migrations_table.sql`: schema_migrations tracking table
- `migrate.py`: Standalone synchronous migration runner (pymysql, loads .env, idempotent)

**Files modified:**
- `init.sql`: Added schema_migrations table at end (Docker first-run gets tracking table)
- `requirements.txt`: Added pymysql==1.* for migrate.py

**DoD verification:**
- migrations/ directory with all 3 SQL files — PASS
- migrate.py exists with full runner logic — PASS
- init.sql includes schema_migrations — PASS
- pymysql pinned in requirements.txt — PASS

### Reviewer Report
<pending>

---

## Expert Notes & Decisions

**2026-05-06**: Task created. Two agents will run in parallel:
- coder-implementer: fixes B1–B6 + W1–W4
- devops-deployer: builds migration system

**Architecture decision on B4 (race condition)**: Chose atomic DB claim (UPDATE WHERE
next_reminder_at = expected_value) over APScheduler max_instances=1 because:
1. max_instances=1 only protects against overlapping runs on ONE process; atomic DB claim
   works across multiple bot replicas too
2. The optimistic locking approach (match exact timestamp) is idiomatic and doesn't require
   APScheduler internals

**Architecture decision on B5**: Advancing next_reminder_at BEFORE sending (as part of
the B4 claim) means transient failures silently skip one cycle. This is the right tradeoff:
Telegram outages are rare and short; infinite retry hammering is worse than one missed
reminder. Permanent failures (bot blocked) are caught and logged.

**Architecture decision on migrate.py**: Using synchronous pymysql (not aiomysql) because
the migration runner is a standalone CLI tool, not part of the async bot. pymysql is a
well-maintained, stable sync driver compatible with MySQL 8 and used widely in Django/Flask.
