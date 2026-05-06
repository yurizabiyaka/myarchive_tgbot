import re
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import ContextTypes

from db.pool import get_pool
from db.schedules import get_schedule, upsert_schedule
from db.users import ensure_user


def _timelength_to_seconds(text: str) -> int | None:
    """Convert a time length string to seconds using timelength library.

    Tries both v2.x (result.seconds) and v1.x (to_seconds()) APIs for compatibility.

    Args:
        text: Time length string (e.g., "1 day", "2 hours").

    Returns:
        Number of seconds, or None if parsing fails.
    """
    try:
        from timelength import TimeLength

        tl = TimeLength(text)
        if hasattr(tl, "result") and hasattr(tl.result, "seconds") and tl.result.seconds:
            return int(tl.result.seconds)
        s = tl.to_seconds()
        if s and s > 0:
            return int(s)
    except Exception:
        pass
    return None


def _parse_schedule_args(args_str: str) -> tuple[int | None, int | None]:
    """Parse /schedule command arguments.

    Supports formats:
    - "3 days" → (interval_seconds, None)
    - "4 items" → (None, items_count)
    - "3 days, 2 items" → (interval_seconds, items_count)
    - "2 items, 3 days" → (interval_seconds, items_count)

    Args:
        args_str: Raw arguments string.

    Returns:
        Tuple of (interval_seconds, items_count), either or both can be None.
        If parsing fails, returns (None, None).
    """
    args_str = args_str.strip()
    if not args_str:
        return (None, None)

    parts = [p.strip() for p in args_str.split(",")]

    interval_seconds = None
    items_count = None

    for part in parts:
        items_match = re.match(r"^(\d+)\s+items?$", part, re.IGNORECASE)
        if items_match:
            items_count = int(items_match.group(1))
            continue

        seconds = _timelength_to_seconds(part)
        if seconds and seconds > 0:
            interval_seconds = seconds
            continue

        # Unrecognized fragment - skip it, do not abort

    if interval_seconds is None and items_count is None:
        return (None, None)

    return (interval_seconds, items_count)


async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /schedule command.

    Display current schedule or set/update the schedule.
    """
    if not update.effective_user or not update.message:
        return

    try:
        pool = get_pool()
        user_id = update.effective_user.id

        await ensure_user(
            pool,
            user_id,
            update.effective_user.username,
            update.effective_user.first_name,
            update.effective_user.last_name,
        )

        args_str = " ".join(context.args) if context.args else ""

        if not args_str:
            schedule = await get_schedule(pool, user_id)
            if not schedule:
                help_text = (
                    "No reminder schedule set.\n\n"
                    "Set a reminder schedule with:\n"
                    "/schedule 1 day\n"
                    "/schedule 5 items\n"
                    "/schedule 1 day, 5 items"
                )
                await update.message.reply_text(help_text)
            else:
                interval_seconds = schedule["interval_seconds"]
                items_count = schedule["items_count"]
                next_reminder = schedule["next_reminder_at"]

                days = interval_seconds // 86400
                hours = (interval_seconds % 86400) // 3600
                minutes = (interval_seconds % 3600) // 60

                interval_str = _format_interval(days, hours, minutes)

                now = datetime.now(timezone.utc).replace(tzinfo=None)
                time_until = next_reminder - now
                until_str = _format_time_until(time_until)

                status_text = (
                    f"You have set reminder interval to {interval_str}.\n"
                    f"I will send you {items_count} random items from your archive "
                    f"at {next_reminder.strftime('%Y/%m/%d %H:%M')} "
                    f"(within {until_str} from now).\n\n"
                    f"To change the interval: /schedule 1 day\n"
                    f"To change items count: /schedule 5 items\n"
                    f"To change both: /schedule 1 day, 5 items\n"
                    f"The first reminder will come within 1 minute."
                )
                await update.message.reply_text(status_text)

            return

        interval_seconds, items_count = _parse_schedule_args(args_str)

        if interval_seconds is None and items_count is None:
            help_text = (
                "Could not parse schedule arguments.\n\n"
                "Usage:\n"
                "/schedule 1 day\n"
                "/schedule 5 items\n"
                "/schedule 1 day, 5 items"
            )
            await update.message.reply_text(help_text)
            return

        schedule = await get_schedule(pool, user_id)

        if interval_seconds is None and schedule:
            interval_seconds = schedule["interval_seconds"]
        elif interval_seconds is None:
            await update.message.reply_text(
                "No existing interval set. Please specify an interval:\n"
                "/schedule 1 day, 5 items"
            )
            return

        if items_count is None:
            items_count = schedule["items_count"] if schedule else 5

        items_count = max(1, min(items_count, 20))

        MIN_INTERVAL = 300  # 5 minutes minimum
        if interval_seconds < MIN_INTERVAL:
            await update.message.reply_text(
                "Minimum reminder interval is 5 minutes. "
                "Please use an interval of at least 5 minutes."
            )
            return

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        next_reminder_at = now + timedelta(seconds=60)

        await upsert_schedule(
            pool, user_id, interval_seconds, items_count, next_reminder_at
        )

        days = interval_seconds // 86400
        hours = (interval_seconds % 86400) // 3600
        minutes = (interval_seconds % 3600) // 60

        interval_str = _format_interval(days, hours, minutes)

        confirmation = (
            f"Reminder schedule updated!\n\n"
            f"Interval: {interval_str}\n"
            f"Items per reminder: {items_count}\n"
            f"First reminder in: 1 minute\n\n"
            f"Tip: Run /schedule at your preferred time to receive reminders at that time of day."
        )
        await update.message.reply_text(confirmation)

    except Exception as e:
        await update.message.reply_text(f"Sorry, something went wrong: {str(e)}")


def _format_interval(days: int, hours: int, minutes: int) -> str:
    """Format interval into human-readable string."""
    parts = []
    if days > 0:
        parts.append(f"{days} day" if days == 1 else f"{days} days")
    if hours > 0:
        parts.append(f"{hours} hour" if hours == 1 else f"{hours} hours")
    if minutes > 0:
        parts.append(f"{minutes} minute" if minutes == 1 else f"{minutes} minutes")
    return ", ".join(parts) if parts else "0 seconds"


def _format_time_until(td: timedelta) -> str:
    """Format timedelta into human-readable string."""
    total_seconds = int(td.total_seconds())
    if total_seconds < 0:
        return "now"
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    return _format_interval(days, hours, minutes)
