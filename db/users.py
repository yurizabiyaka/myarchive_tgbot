import aiomysql


async def ensure_user(
    pool: aiomysql.Pool,
    user_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
) -> None:
    """Ensure a user exists in the database (idempotent).

    If the user already exists, this is a no-op.

    Args:
        pool: Database connection pool.
        user_id: Telegram user ID.
        username: Telegram username (optional).
        first_name: User's first name (optional).
        last_name: User's last name (optional).
    """
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT IGNORE INTO users (id, username, first_name, last_name)
                VALUES (%s, %s, %s, %s)
                """,
                (user_id, username, first_name, last_name),
            )
            await conn.commit()


async def delete_user(pool: aiomysql.Pool, user_id: int) -> None:
    """Delete a user and all associated items from the database.

    The CASCADE foreign key constraint automatically deletes all items.

    Args:
        pool: Database connection pool.
        user_id: Telegram user ID.
    """
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
            await conn.commit()
