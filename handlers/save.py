from telegram import Message, MessageEntity, MessageOriginChannel, MessageOriginChat, MessageOriginHiddenUser, MessageOriginUser, Update
from telegram.ext import ContextTypes, filters

from db.items import save_item
from db.pool import get_pool


def url_filter(message: Message) -> bool:
    """Check if a message contains URLs in its entities."""
    if not message.entities:
        return False
    for entity in message.entities:
        if entity.type in (MessageEntity.URL, MessageEntity.TEXT_LINK):
            return True
    return False


class SaveFilter(filters.BaseFilter):
    """Custom filter to match forwarded messages or messages with URLs."""

    async def filter(self, message: Message) -> bool:
        """Return True if the message is forwarded or contains URLs."""
        # Check for forwarded message
        if message.forward_origin:
            return True
        # Check for URLs
        return url_filter(message)


async def save_forwarded_or_url(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle forwarded messages and URL-bearing messages.

    Saves them to the database with appropriate metadata.
    """
    if not update.message or not update.effective_user:
        return

    message = update.message

    try:
        pool = get_pool()

        # Check for forwarded message first
        if message.forward_origin:
            content = _extract_forward_content(message.forward_origin)
            text = message.text or message.caption
            await save_item(
                pool,
                update.effective_user.id,
                "forwarded_message",
                content,
                text,
            )
            await update.message.reply_text("Saved!")
            return

        # Check for URLs
        if message.entities:
            for entity in message.entities:
                if entity.type == MessageEntity.URL:
                    url_start = entity.offset
                    url_end = url_start + entity.length
                    content = message.text[url_start:url_end]
                    text = message.text
                    await save_item(
                        pool,
                        update.effective_user.id,
                        "link",
                        content,
                        text,
                    )
                    await update.message.reply_text("Saved!")
                    return
                elif entity.type == MessageEntity.TEXT_LINK:
                    content = entity.url
                    text = message.text
                    await save_item(
                        pool,
                        update.effective_user.id,
                        "link",
                        content,
                        text,
                    )
                    await update.message.reply_text("Saved!")
                    return

    except Exception as e:
        await update.message.reply_text(
            f"Sorry, something went wrong: {str(e)}"
        )


def _extract_forward_content(forward_origin) -> str:
    """Extract content description from a MessageOrigin object.

    Args:
        forward_origin: A MessageOrigin object (Channel, User, Chat, or HiddenUser).

    Returns:
        A string describing the forwarded message origin.
    """
    if isinstance(forward_origin, MessageOriginChannel):
        channel_name = forward_origin.chat.title or "Unknown Channel"
        return f"Forwarded from {channel_name}"

    if isinstance(forward_origin, MessageOriginUser):
        user_name = forward_origin.sender_user.full_name or "Unknown User"
        return f"Forwarded from {user_name}"

    if isinstance(forward_origin, MessageOriginChat):
        chat_name = forward_origin.sender_chat.title or "Unknown Chat"
        return f"Forwarded from {chat_name}"

    if isinstance(forward_origin, MessageOriginHiddenUser):
        return "Forwarded from Hidden User"

    return "Forwarded message"
