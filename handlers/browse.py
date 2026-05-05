from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from db.items import (
    count_items,
    count_search,
    delete_item,
    list_items,
    search_items,
)
from db.pool import get_pool

MAX_QUERY_LEN = 40


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user:
        return
    try:
        pool = get_pool()
        items = await list_items(pool, update.effective_user.id, 0, 1)
        total = await count_items(pool, update.effective_user.id)
        text, markup = render_card(items, total, 0, ("list", None))
        await update.message.reply_text(text, reply_markup=markup)
    except Exception as e:
        await update.message.reply_text(f"Sorry, something went wrong: {e}")


async def find_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.message:
        return
    try:
        args = update.message.text.split(maxsplit=1)
        if len(args) < 2:
            await update.message.reply_text(
                "Please provide keywords to search for.\nUsage: /find <keywords>"
            )
            return
        query = args[1]
        pool = get_pool()
        items = await search_items(pool, update.effective_user.id, query, 0, 1)
        total = await count_search(pool, update.effective_user.id, query)
        text, markup = render_card(items, total, 0, ("find", query))
        await update.message.reply_text(text, reply_markup=markup)
    except Exception as e:
        await update.message.reply_text(f"Sorry, something went wrong: {e}")


def _tq(query_str: str | None) -> str:
    return (query_str or "")[:MAX_QUERY_LEN]


def render_card(
    items: list[dict],
    total: int,
    page: int,
    context: tuple[str, str | None],
) -> tuple[str, InlineKeyboardMarkup | None]:
    """Render a single-item card with prev/delete/next navigation.

    page is the 0-based item index; one item is shown per page.
    """
    mode, query_str = context

    if not items:
        return ("No items found.", None)

    item = items[0]
    saved_at = item["saved_at"]
    saved_at_str = saved_at.strftime("%Y-%m-%d %H:%M") if isinstance(saved_at, datetime) else str(saved_at)

    text_content = item["text"] or ""
    text_display = (text_content[:200] + "...") if len(text_content) > 200 else text_content

    card_text = f"[{page + 1} / {total}]\n\nType: {item['type']}\nSaved: {saved_at_str}\n\n{item['content']}\n"
    if text_display:
        card_text += f"\n{text_display}\n"

    buttons = []
    item_id = item["id"]
    tq = _tq(query_str)

    if page > 0:
        cb = f"list:page:{page - 1}" if mode == "list" else f"find:{tq}:page:{page - 1}"
        buttons.append(InlineKeyboardButton("<< Prev", callback_data=cb))

    if mode == "list":
        buttons.append(InlineKeyboardButton("Delete", callback_data=f"del:list:{item_id}:page:{page}"))
    else:
        buttons.append(InlineKeyboardButton("Delete", callback_data=f"del:find:{tq}:{item_id}:page:{page}"))

    if page + 1 < total:
        cb = f"list:page:{page + 1}" if mode == "list" else f"find:{tq}:page:{page + 1}"
        buttons.append(InlineKeyboardButton("Next >>", callback_data=cb))

    markup = InlineKeyboardMarkup([buttons]) if buttons else None
    return (card_text, markup)


async def callback_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not update.effective_user:
        return
    try:
        # "list:page:<N>"
        page = int(query.data.split(":")[2])
        pool = get_pool()
        items = await list_items(pool, update.effective_user.id, page, 1)
        total = await count_items(pool, update.effective_user.id)
        text, markup = render_card(items, total, page, ("list", None))
        await query.edit_message_text(text, reply_markup=markup)
        await query.answer()
    except Exception as e:
        await query.answer(f"Error: {e}", show_alert=True)


async def callback_find(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not update.effective_user:
        return
    try:
        # "find:<query>:page:<N>"
        parts = query.data.split(":", 3)
        search_query = parts[1]
        page = int(parts[3])
        pool = get_pool()
        items = await search_items(pool, update.effective_user.id, search_query, page, 1)
        total = await count_search(pool, update.effective_user.id, search_query)
        text, markup = render_card(items, total, page, ("find", search_query))
        await query.edit_message_text(text, reply_markup=markup)
        await query.answer()
    except Exception as e:
        await query.answer(f"Error: {e}", show_alert=True)


async def callback_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not update.effective_user:
        return
    try:
        # "del:list:<item_id>:page:<N>"  or  "del:find:<query>:<item_id>:page:<N>"
        parts = query.data.split(":", 5)
        mode = parts[1]

        if mode == "list":
            item_id = int(parts[2])
            page = int(parts[4])
            search_query = None
        else:
            search_query = parts[2]
            item_id = int(parts[3])
            page = int(parts[5])

        pool = get_pool()
        await delete_item(pool, update.effective_user.id, item_id)

        if mode == "list":
            total = await count_items(pool, update.effective_user.id)
            # Stay on same page index, or back one if we deleted the last item on this page
            page = min(page, max(0, total - 1))
            items = await list_items(pool, update.effective_user.id, page, 1)
            text, markup = render_card(items, total, page, ("list", None))
        else:
            total = await count_search(pool, update.effective_user.id, search_query)
            page = min(page, max(0, total - 1))
            items = await search_items(pool, update.effective_user.id, search_query, page, 1)
            text, markup = render_card(items, total, page, ("find", search_query))

        await query.edit_message_text(text, reply_markup=markup)
        await query.answer()
    except Exception as e:
        await query.answer(f"Error: {e}", show_alert=True)
