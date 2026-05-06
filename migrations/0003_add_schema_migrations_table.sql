-- Migration 0003: Add schema_migrations tracking table
--
-- NOTE: The migrate.py runner bootstraps this table before querying it,
-- so this migration file exists for completeness and auditability.
-- Running it via the runner is safe (CREATE TABLE IF NOT EXISTS is idempotent).

CREATE TABLE IF NOT EXISTS schema_migrations (
    id         VARCHAR(64) PRIMARY KEY,
    applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
