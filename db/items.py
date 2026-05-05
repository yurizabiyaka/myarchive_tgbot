import aiomysql


async def save_item(
    pool: aiomysql.Pool,
    user_id: int,
    type_: str,
    content: str,
    text: str | None,
) -> None:
    """Save an item to the database.

    Args:
        pool: Database connection pool.
        user_id: Telegram user ID.
        type_: Item type ('link' or 'forwarded_message').
        content: Item content (URL or forwarded message reference).
        text: Optional text or caption associated with the item.
    """
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO items (user_id, type, content, text)
                VALUES (%s, %s, %s, %s)
                """,
                (user_id, type_, content, text),
            )
            await conn.commit()


async def list_items(
    pool: aiomysql.Pool, user_id: int, offset: int, limit: int
) -> list[dict]:
    """List items for a user with pagination.

    Args:
        pool: Database connection pool.
        user_id: Telegram user ID.
        offset: Number of items to skip.
        limit: Maximum number of items to return.

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
                ORDER BY saved_at DESC
                LIMIT %s OFFSET %s
                """,
                (user_id, limit, offset),
            )
            return await cur.fetchall()


async def count_items(pool: aiomysql.Pool, user_id: int) -> int:
    """Count total items for a user.

    Args:
        pool: Database connection pool.
        user_id: Telegram user ID.

    Returns:
        Total number of items.
    """
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT COUNT(*) FROM items WHERE user_id = %s",
                (user_id,),
            )
            result = await cur.fetchone()
            return result[0] if result else 0


async def search_items(
    pool: aiomysql.Pool, user_id: int, query: str, offset: int, limit: int
) -> list[dict]:
    """Search items using full-text search.

    Args:
        pool: Database connection pool.
        user_id: Telegram user ID.
        query: Full-text search query.
        offset: Number of items to skip.
        limit: Maximum number of items to return.

    Returns:
        List of matching item dictionaries with keys: id, type, content, text, saved_at.
    """
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT id, type, content, text, saved_at
                FROM items
                WHERE user_id = %s AND MATCH(content, text) AGAINST(%s IN BOOLEAN MODE)
                ORDER BY saved_at DESC
                LIMIT %s OFFSET %s
                """,
                (user_id, query, limit, offset),
            )
            return await cur.fetchall()


async def count_search(pool: aiomysql.Pool, user_id: int, query: str) -> int:
    """Count total search results for a user.

    Args:
        pool: Database connection pool.
        user_id: Telegram user ID.
        query: Full-text search query.

    Returns:
        Total number of matching items.
    """
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT COUNT(*) FROM items
                WHERE user_id = %s AND MATCH(content, text) AGAINST(%s IN BOOLEAN MODE)
                """,
                (user_id, query),
            )
            result = await cur.fetchone()
            return result[0] if result else 0


async def delete_item(pool: aiomysql.Pool, user_id: int, item_id: int) -> None:
    """Delete an item, ensuring the user owns it.

    Args:
        pool: Database connection pool.
        user_id: Telegram user ID.
        item_id: Item ID to delete.
    """
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM items WHERE id = %s AND user_id = %s",
                (item_id, user_id),
            )
            await conn.commit()
