import aiomysql

from config import Config

_pool: aiomysql.Pool | None = None


async def init_pool(cfg: Config) -> None:
    """Initialize the database connection pool.

    Args:
        cfg: Configuration object with database connection parameters.
    """
    global _pool
    _pool = await aiomysql.create_pool(
        host=cfg.db_host,
        port=cfg.db_port,
        user=cfg.db_user,
        password=cfg.db_password,
        db=cfg.db_name,
        minsize=cfg.db_pool_min,
        maxsize=cfg.db_pool_max,
    )


def get_pool() -> aiomysql.Pool:
    """Get the database connection pool.

    Returns:
        The initialized connection pool.

    Raises:
        RuntimeError: If the pool has not been initialized.
    """
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_pool() first.")
    return _pool
