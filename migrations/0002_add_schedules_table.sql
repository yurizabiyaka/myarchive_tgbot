-- Migration 0002: Add schedules table for /schedule reminder feature

CREATE TABLE IF NOT EXISTS schedules (
    user_id          BIGINT PRIMARY KEY,
    interval_seconds INT UNSIGNED NOT NULL,
    items_count      INT UNSIGNED NOT NULL DEFAULT 5,
    next_reminder_at DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
