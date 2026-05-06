import aiomysql


async def get_schedule(pool: aiomysql.Pool, user_id: int) -> dict | None:
    """Get the reminder schedule for a user.

    Args:
        pool: Database connection pool.
        user_id: Telegram user ID.

    Returns:
        Schedule dictionary with keys: user_id, interval_seconds, items_count, next_reminder_at.
        None if no schedule exists.
    """
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT user_id, interval_seconds, items_count, next_reminder_at
                FROM schedules
                WHERE user_id = %s
                """,
                (user_id,),
            )
            return await cur.fetchone()


async def upsert_schedule(
    pool: aiomysql.Pool,
    user_id: int,
    interval_seconds: int,
    items_count: int,
    next_reminder_at,
) -> None:
    """Insert or update a reminder schedule for a user.

    Args:
        pool: Database connection pool.
        user_id: Telegram user ID.
        interval_seconds: Interval between reminders in seconds.
        items_count: Number of items to send per reminder.
        next_reminder_at: Next reminder datetime.
    """
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO schedules (user_id, interval_seconds, items_count, next_reminder_at)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    interval_seconds = VALUES(interval_seconds),
                    items_count = VALUES(items_count),
                    next_reminder_at = VALUES(next_reminder_at)
                """,
                (user_id, interval_seconds, items_count, next_reminder_at),
            )
            await conn.commit()


async def update_next_reminder(
    pool: aiomysql.Pool, user_id: int, next_reminder_at
) -> None:
    """Update the next_reminder_at time for a user's schedule.

    Args:
        pool: Database connection pool.
        user_id: Telegram user ID.
        next_reminder_at: Next reminder datetime.
    """
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE schedules
                SET next_reminder_at = %s
                WHERE user_id = %s
                """,
                (next_reminder_at, user_id),
            )
            await conn.commit()


async def get_due_schedules(pool: aiomysql.Pool) -> list[dict]:
    """Get all schedules where the next reminder is due (past or present).

    Args:
        pool: Database connection pool.

    Returns:
        List of schedule dictionaries with keys: user_id, interval_seconds, items_count.
    """
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT user_id, interval_seconds, items_count, next_reminder_at
                FROM schedules
                WHERE next_reminder_at <= NOW()
                """
            )
            return await cur.fetchall()


async def claim_and_advance_schedule(
    pool: aiomysql.Pool,
    user_id: int,
    expected_next,
    interval_seconds: int,
) -> bool:
    """Atomically advance next_reminder_at to prevent duplicate sends.

    Uses UPDATE WHERE next_reminder_at = expected_next as an optimistic lock.
    Returns True if this process claimed the schedule, False if another tick
    already claimed it (rowcount == 0).

    Args:
        pool: Database connection pool.
        user_id: Telegram user ID.
        expected_next: The next_reminder_at value read from get_due_schedules.
        interval_seconds: Reminder interval in seconds.

    Returns:
        True if claim succeeded, False otherwise.
    """
    from datetime import datetime, timedelta, timezone
    new_next = max(
        datetime.now(timezone.utc).replace(tzinfo=None),
        expected_next + timedelta(seconds=interval_seconds),
    )
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


async def get_random_items(
    pool: aiomysql.Pool, user_id: int, count: int
) -> list[dict]:
    """Get random items for a user.

    Args:
        pool: Database connection pool.
        user_id: Telegram user ID.
        count: Number of random items to fetch.

    Returns:
        List of item dictionaries with keys: id, type, content, text, saved_at.
    """
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT id, type, content, text, saved_at
                FROM items
                WHERE user_id = %s
                ORDER BY RAND()
                LIMIT %s
                """,
                (user_id, count),
            )
            return await cur.fetchall()
