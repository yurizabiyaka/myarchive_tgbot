from telegram import Update
from telegram.ext import ContextTypes


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /help command.

    Displays the bot description and list of available commands.
    """
    if not update.effective_chat:
        return

    help_text = """
🤖 *myarchive Bot*

Your personal saver for links and forwarded messages. Save your finds, browse them anytime, and search by keyword.

*Available Commands:*

/start – Register and start using the bot
/help – Show this help message
/list – Browse all your saved items (paginated)
/find <keywords> – Search your items by keyword
/forgetme – Delete your account and all saved items
"""

    try:
        await update.message.reply_text(help_text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(
            f"Sorry, something went wrong: {str(e)}"
        )
