from telegram import Update
from telegram.ext import ContextTypes

from db.pool import get_pool
from db.users import ensure_user


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command.

    Registers the user in the database and sends a welcome message.
    """
    if not update.effective_user or not update.effective_chat:
        return

    try:
        pool = get_pool()
        await ensure_user(
            pool,
            update.effective_user.id,
            update.effective_user.username,
            update.effective_user.first_name,
            update.effective_user.last_name,
        )

        welcome_text = (
            f"Welcome, {update.effective_user.first_name or 'Friend'}! 👋\n\n"
            "I'm myarchive, your personal link and message saver.\n\n"
            "Use /help to see all commands."
        )
        await update.message.reply_text(welcome_text)
    except Exception as e:
        await update.message.reply_text(
            f"Sorry, something went wrong: {str(e)}"
        )
