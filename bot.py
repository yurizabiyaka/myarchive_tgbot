import logging

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
)

from config import config
from db.pool import init_pool
from handlers.browse import (
    callback_delete,
    callback_find,
    callback_list,
    find_command,
    list_command,
)
from handlers.forgetme import cancel_forgetme, confirm_forgetme, forgetme
from handlers.help import help_command
from handlers.save import SaveFilter, save_forwarded_or_url
from handlers.start import start

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def post_init(application: Application) -> None:
    """Initialize the database pool after the application starts."""
    logger.info("Initializing database pool...")
    await init_pool(config)
    logger.info("Database pool initialized.")


def main() -> None:
    """Start the Telegram bot."""
    # Build the Application
    application = Application.builder().token(config.bot_token).post_init(post_init).build()

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(CommandHandler("find", find_command))
    application.add_handler(CommandHandler("forgetme", forgetme))

    # Register message handler for forwarded messages and URLs
    application.add_handler(
        MessageHandler(SaveFilter(), save_forwarded_or_url)
    )

    # Register callback query handlers
    application.add_handler(CallbackQueryHandler(callback_list, pattern=r"^list:"))
    application.add_handler(CallbackQueryHandler(callback_find, pattern=r"^find:"))
    application.add_handler(CallbackQueryHandler(callback_delete, pattern=r"^del:"))
    application.add_handler(
        CallbackQueryHandler(confirm_forgetme, pattern=r"^confirm_forgetme$")
    )
    application.add_handler(
        CallbackQueryHandler(cancel_forgetme, pattern=r"^cancel_forgetme$")
    )

    # Start the bot
    logger.info("Starting bot polling...")
    application.run_polling()


if __name__ == "__main__":
    main()
