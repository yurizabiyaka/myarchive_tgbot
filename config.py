import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class Config:
    """Telegram bot and database configuration."""

    bot_token: str
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    db_pool_min: int
    db_pool_max: int


def _load_config() -> Config:
    """Load configuration from environment variables."""
    load_dotenv()

    return Config(
        bot_token=os.getenv("BOT_TOKEN", ""),
        db_host=os.getenv("DB_HOST", ""),
        db_port=int(os.getenv("DB_PORT", "3306")),
        db_name=os.getenv("DB_NAME", ""),
        db_user=os.getenv("DB_USER", ""),
        db_password=os.getenv("DB_PASSWORD", ""),
        db_pool_min=int(os.getenv("DB_POOL_MIN", "1")),
        db_pool_max=int(os.getenv("DB_POOL_MAX", "5")),
    )


config = _load_config()
