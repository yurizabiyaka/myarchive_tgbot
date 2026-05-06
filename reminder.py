import logging
from datetime import datetime, timedelta, timezone

from telegram.error import ChatMigrated, Forbidden
from telegram.ext import ContextTypes

from db.items import count_items
from db.pool import get_pool
from db.schedules import (
    claim_and_advance_schedule,
    get_due_schedules,
    get_random_items,
)

logger = logging.getLogger(__name__)


async def send_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Periodic job to send due reminders to users.

    Runs every 60 seconds. Atomically claims each due schedule before
    sending to prevent duplicate sends on overlapping job ticks.

    Flow per due schedule:
    1. Atomically advance next_reminder_at (optimistic lock via UPDATE WHERE).
       If rowcount == 0, another tick already claimed it — skip.
    2. Fetch random items for the user.
    3. Send reminder message, splitting at Telegram's 4096-char limit.
    4. Permanent failures (Forbidden, ChatMigrated) are caught and logged;
       schedule remains advanced (no infinite retry).
    """
    try:
        pool = get_pool()
        due_schedules = await get_due_schedules(pool)

        for schedule in due_schedules:
            user_id = schedule["user_id"]
            interval_seconds = schedule["interval_seconds"]
            items_count = schedule["items_count"]
            expected_next = schedule["next_reminder_at"]

            try:
                # Atomically claim this schedule tick — prevents duplicate sends
                claimed = await claim_and_advance_schedule(
                    pool, user_id, expected_next, interval_seconds
                )
                if not claimed:
                    logger.info(
                        f"Schedule for user {user_id} already claimed by another tick, skipping."
                    )
                    continue

                total_items = await count_items(pool, user_id)
                if total_items == 0:
                    continue

                items = await get_random_items(pool, user_id, items_count)
                if not items:
                    continue

                reminder_text = _format_reminder_message(items)
                for msg in _split_message(reminder_text):
                    await context.bot.send_message(chat_id=user_id, text=msg)

            except (Forbidden, ChatMigrated) as e:
                logger.warning(
                    f"Permanent send failure for user {user_id}: {e}. "
                    "Schedule advanced - no retry."
                )
            except Exception as e:
                logger.error(f"Error processing reminder for user {user_id}: {e}")
                continue

    except Exception as e:
        logger.error(f"Error in send_reminders job: {e}")


def _split_message(text: str, max_len: int = 4096) -> list[str]:
    """Split text into chunks of at most max_len characters, splitting on newlines.

    Args:
        text: Message text to split.
        max_len: Maximum length per chunk (default 4096, Telegram's limit).

    Returns:
        List of message chunks, each at most max_len characters.
    """
    if len(text) <= max_len:
        return [text]
    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


def _format_reminder_message(items: list[dict]) -> str:
    """Format reminder message with random items.

    Args:
        items: List of item dictionaries with keys: type, content, text, saved_at.

    Returns:
        Formatted message string.
    """
    lines = [f"Reminder! Here are {len(items)} items from your archive:\n"]

    for idx, item in enumerate(items, 1):
        item_type = item["type"]
        content = item["content"]
        text = item.get("text") or ""
        saved_at = item["saved_at"]

        saved_at_str = (
            saved_at.strftime("%Y-%m-%d %H:%M")
            if isinstance(saved_at, datetime)
            else str(saved_at)
        )

        lines.append(f"[{idx}/{len(items)}] {item_type}")
        lines.append(f"Saved: {saved_at_str}")
        lines.append(content)

        if text and text != content:
            text_snippet = text[:200] + "..." if len(text) > 200 else text
            lines.append(text_snippet)

        lines.append("")

    return "\n".join(lines).strip()
