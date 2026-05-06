-- Initialize myarchive database schema
-- This script runs automatically on MySQL container first startup via docker-entrypoint

-- users table: stores Telegram user metadata
CREATE TABLE IF NOT EXISTS users (
    id            BIGINT PRIMARY KEY,
    username      VARCHAR(255),
    first_name    VARCHAR(255),
    last_name     VARCHAR(255),
    registered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- items table: stores saved links and forwarded messages
CREATE TABLE IF NOT EXISTS items (
    id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id     BIGINT NOT NULL,
    type        ENUM('link','forwarded_message') NOT NULL,
    content     TEXT NOT NULL,
    text        TEXT,
    saved_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FULLTEXT INDEX ft_items (content, text)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- schedules table: stores reminder schedules for users
CREATE TABLE IF NOT EXISTS schedules (
    user_id          BIGINT PRIMARY KEY,
    interval_seconds INT UNSIGNED NOT NULL,
    items_count      INT UNSIGNED NOT NULL DEFAULT 5,
    next_reminder_at DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- schema_migrations table: tracks applied DB migrations (used by migrate.py)
CREATE TABLE IF NOT EXISTS schema_migrations (
    id         VARCHAR(64) PRIMARY KEY,
    applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
