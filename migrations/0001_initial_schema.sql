-- Migration 0001: Initial schema -- users and items tables

CREATE TABLE IF NOT EXISTS users (
    id            BIGINT PRIMARY KEY,
    username      VARCHAR(255),
    first_name    VARCHAR(255),
    last_name     VARCHAR(255),
    registered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

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
