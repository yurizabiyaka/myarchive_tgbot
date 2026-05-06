#!/usr/bin/env python3
"""Database migration runner for myarchive_tgbot.

Usage:
    python migrate.py

Reads DB connection from .env (same variables as the bot):
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

Applies all pending migrations from the migrations/ directory in order.
Records each applied migration in the schema_migrations table.
Exits non-zero on any failure (no partial applies within a migration).
"""
import os
import sys
from pathlib import Path

import pymysql
from dotenv import load_dotenv

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def get_connection() -> pymysql.Connection:
    """Create a database connection using env vars from .env."""
    load_dotenv()
    return pymysql.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", 3306)),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        autocommit=False,
        charset="utf8mb4",
    )


def bootstrap_migrations_table(conn: pymysql.Connection) -> None:
    """Ensure schema_migrations table exists before we try to query it.

    This is a bootstrap step: the table may not exist yet on a fresh DB,
    so we create it unconditionally before checking applied migrations.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id         VARCHAR(64) PRIMARY KEY,
                applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    conn.commit()


def get_applied(conn: pymysql.Connection) -> set:
    """Return the set of migration IDs already recorded in schema_migrations."""
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM schema_migrations")
        return {row[0] for row in cur.fetchall()}


def apply_migration(conn: pymysql.Connection, migration_id: str, sql: str) -> None:
    """Execute all statements in sql and record migration_id in schema_migrations.

    All statements plus the tracking INSERT are executed in a single transaction.
    On any error the transaction is rolled back and the exception is re-raised.
    """
    with conn.cursor() as cur:
        # Execute each non-empty statement from the SQL file
        for statement in sql.split(";"):
            stmt = statement.strip()
            if stmt and not stmt.startswith("--"):
                cur.execute(stmt)
        # Record the migration as applied
        cur.execute(
            "INSERT INTO schema_migrations (id) VALUES (%s)",
            (migration_id,),
        )
    conn.commit()


def main() -> None:
    """Run all pending migrations in order."""
    try:
        conn = get_connection()
    except KeyError as e:
        print(f"Missing required environment variable: {e}", file=sys.stderr)
        sys.exit(1)
    except pymysql.Error as e:
        print(f"Failed to connect to database: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        bootstrap_migrations_table(conn)
        applied = get_applied(conn)

        migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        if not migration_files:
            print("No migration files found in migrations/.")
            return

        pending = [f for f in migration_files if f.stem not in applied]

        if not pending:
            print("All migrations already applied. Database is up to date.")
            return

        for path in pending:
            migration_id = path.stem
            print(f"[apply] {migration_id} ...")
            sql = path.read_text()
            try:
                apply_migration(conn, migration_id, sql)
                print(f"[done]  {migration_id}")
            except pymysql.Error as e:
                print(
                    f"[FAIL]  {migration_id}: {e}",
                    file=sys.stderr,
                )
                conn.rollback()
                sys.exit(1)

        # Report skipped (already applied) migrations for transparency
        skipped = [f.stem for f in migration_files if f.stem in applied]
        for mid in skipped:
            print(f"[skip]  {mid} (already applied)")

        print(f"\nDone. Applied {len(pending)} migration(s).")

    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
