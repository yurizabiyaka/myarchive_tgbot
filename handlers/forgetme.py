from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from db.pool import get_pool
from db.users import delete_user


async def forgetme(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /forgetme command.

    Sends a confirmation message with buttons to confirm or cancel deletion.
    """
    if not update.effective_chat:
        return

    try:
        keyboard = [
            [
                InlineKeyboardButton(
                    "Yes, delete everything",
                    callback_data="confirm_forgetme",
                ),
                InlineKeyboardButton(
                    "Cancel",
                    callback_data="cancel_forgetme",
                ),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "Are you sure you want to delete your account and all saved items? "
            "This action cannot be undone.",
            reply_markup=reply_markup,
        )
    except Exception as e:
        await update.message.reply_text(
            f"Sorry, something went wrong: {str(e)}"
        )


async def confirm_forgetme(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle the confirmation callback for /forgetme.

    Deletes the user and all their items.
    """
    query = update.callback_query
    if not query or not query.message or not update.effective_user:
        return

    try:
        pool = get_pool()
        await delete_user(pool, update.effective_user.id)

        await query.answer()
        await query.edit_message_text(
            "Your account and all saved items have been deleted. Goodbye!"
        )
    except Exception as e:
        await query.answer()
        await query.edit_message_text(
            f"Sorry, something went wrong: {str(e)}"
        )


async def cancel_forgetme(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle the cancellation callback for /forgetme."""
    query = update.callback_query
    if not query or not query.message:
        return

    try:
        await query.answer()
        await query.edit_message_text("Cancelled.")
    except Exception as e:
        await query.answer()
        await query.edit_message_text(
            f"Sorry, something went wrong: {str(e)}"
        )
