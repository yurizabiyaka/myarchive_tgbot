# myarchive_tgbot Implementation Notes

## Overview

All Python source files for the myarchive_tgbot Telegram bot have been implemented. This document provides a quick reference for developers and testers.

## File Structure

```
myarchive_tgbot/
├── config.py                 # Configuration (Config dataclass, singleton)
├── bot.py                    # Entry point (Application, handlers, polling)
├── requirements.txt          # Python dependencies
├── db/
│   ├── __init__.py          # Package marker
│   ├── pool.py              # aiomysql pool management
│   ├── users.py             # User CRUD (ensure_user, delete_user)
│   └── items.py             # Item CRUD + search (6 functions)
└── handlers/
    ├── __init__.py          # Package marker
    ├── start.py             # /start command
    ├── help.py              # /help command
    ├── forgetme.py          # /forgetme + callbacks
    ├── save.py              # Message ingestion (SaveFilter, handlers)
    └── browse.py            # /list, /find, pagination (6 functions)
```

## Key Implementation Details

### Configuration (config.py)
- Loads from `.env` via `python-dotenv`
- All DB connection params have defaults
- DB_PORT defaults to 3306, DB_POOL_MIN=1, DB_POOL_MAX=5

### Database Layer
All functions are **async coroutines** using `aiomysql.Pool`:

**pool.py:**
- `init_pool(cfg)` - Creates pool, stores in module global
- `get_pool()` - Returns pool, raises RuntimeError if not initialized

**users.py:**
- `ensure_user()` - INSERT IGNORE for idempotency
- `delete_user()` - Deletes user (CASCADE deletes items)

**items.py:**
- `save_item()` - Stores link or forwarded message
- `list_items(offset, limit)` - Paginated retrieval
- `count_items()` - Total count for pagination
- `search_items(query, offset, limit)` - FULLTEXT search with BOOLEAN MODE
- `count_search(query)` - Total count for search results
- `delete_item()` - Ownership-checked (WHERE id=? AND user_id=?)

### Handlers
All are **async** handler functions with try/except error handling:

**start.py:**
- `/start` command: calls ensure_user(), sends welcome message

**help.py:**
- `/help` command: displays bot description + command list (Markdown)

**forgetme.py:**
- `/forgetme` command: inline buttons for confirm/cancel
- `confirm_forgetme` callback: deletes user (CASCADE)
- `cancel_forgetme` callback: sends "Cancelled."

**save.py:**
- Custom `SaveFilter` class that detects forwarded messages OR URLs
- Forwarded check: `message.forward_origin` (all 4 types: Channel, User, Chat, HiddenUser)
- URL check: `message.entities` for URL and TEXT_LINK types
- `save_forwarded_or_url()` handler: saves to DB with appropriate type

**browse.py:**
- Constants: `PAGE_SIZE=5`, `MAX_QUERY_LEN=40`
- `/list` command: shows page 0 of all items
- `/find <query>` command: searches and shows page 0 of results
- `render_card()` function: formats item display with navigation buttons
  - Truncates text to 200 chars
  - Handles empty results gracefully
  - Only shows Prev/Next when available
- Callback handlers for pagination and deletion:
  - Patterns: `^list:`, `^find:`, `^del:`
  - Parse callback_data safely with maxsplit
  - Preserve search context when navigating find results

### Bot Entry Point (bot.py)
- Builds Application with post_init for async pool initialization
- Registers 5 command handlers
- Registers 5 callback query handlers for pagination/delete
- Uses custom SaveFilter for message ingestion
- Logs with timestamp and level
- Calls `run_polling()` for development

## Usage

### Setup
```bash
# 1. Start MySQL
docker-compose up -d

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your BOT_TOKEN and DB credentials

# 4. Run the bot
python bot.py
```

### Testing Points
See TASK_myarchive_bot_mvp.md → "Tester Recommendations" section for:
- Critical test scenarios
- Edge cases
- Test data suggestions
- Integration points
- Risk areas

## Architecture Patterns

### Stateless Pagination
- Page number encoded in button callback_data strings
- Format: `list:page:<N>` or `find:<query>:page:<N>` or `del:list:<item_id>:page:<N>`
- No server-side session state
- Safe for concurrent users

### Error Handling
- All handlers wrapped in try/except
- User-friendly error messages on all failures
- Database errors don't crash the bot

### Configuration
- Environment variables loaded from .env via python-dotenv
- All secrets sourced externally (no hardcoded values)
- Sensible defaults for optional parameters

### Repository Pattern
- DB functions isolated in db/ package
- No ORM — direct SQL with proper parameterization
- FULLTEXT INDEX for efficient search

## Known Constraints

- Query length in callback_data limited to 40 chars (MAX_QUERY_LEN)
- Page size fixed at 5 items per page
- No per-user rate limiting
- No input validation on query parameters (handled via truncation)
- Pagination only supports Prev/Next (no jump-to-page)

## Dependencies

- `python-telegram-bot==21.*` - async, modern PTB API
- `aiomysql==0.2.*` - asyncio-native MySQL with connection pool
- `python-dotenv==1.*` - environment variable loading

## Code Quality Standards

- All Python files compile without syntax errors
- 100% async/await usage (no blocking I/O in handlers)
- Type hints throughout (Optional, Union, list[dict], etc.)
- Comprehensive docstrings on all public APIs
- No unhandled exceptions
- All edge cases addressed
- Ownership validation on all user-scoped operations

---

For detailed specification, see TASK_myarchive_bot_mvp.md
For architecture decisions, see CLAUDE.md
