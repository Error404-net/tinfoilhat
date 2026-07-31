"""
Database module for the Tinfoil Hat Competition application.

This module handles database connections and schema initialization.
"""

import datetime
import logging
import sqlite3
from pathlib import Path

import click
from flask import current_app, g
from flask.cli import with_appcontext

logger = logging.getLogger(__name__)


def adapt_datetime_iso(val):
    """
    Adapt datetime.datetime to ISO 8601 format string for SQLite storage.

    :param val: The datetime object to adapt
    :type val: datetime.datetime
    :return: ISO formatted date string
    :rtype: str
    """
    return val.isoformat()


def convert_timestamp(val):
    """
    Convert SQLite timestamp string to datetime.datetime object.

    :param val: The timestamp value from the database
    :type val: bytes
    :return: A datetime object
    :rtype: datetime.datetime
    """
    try:
        return datetime.datetime.fromisoformat(val.decode())
    except (ValueError, AttributeError):
        # Fall back for older format timestamps without timezone info
        try:
            return datetime.datetime.strptime(val.decode(), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            # Final fallback for any other timestamp format
            return datetime.datetime.fromisoformat(val.decode().split(".")[0])


def register_custom_converters():
    """
    Register custom adapters and converters for SQLite to handle timestamps properly.
    """
    # Register the adapter for datetime objects
    sqlite3.register_adapter(datetime.datetime, adapt_datetime_iso)

    # Register the converter for timestamp fields
    sqlite3.register_converter("timestamp", convert_timestamp)


def get_db():
    """
    Get a database connection.

    :return: SQLite database connection
    :rtype: sqlite3.Connection
    """
    if "db" not in g:
        # Register custom timestamp converters to avoid deprecation warnings
        register_custom_converters()

        g.db = sqlite3.connect(current_app.config["DATABASE"], detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row

    return g.db


def close_db(e=None):
    """
    Close the database connection.

    :param e: Error that triggered the close, defaults to None
    :type e: Exception, optional
    """
    db = g.pop("db", None)

    if db is not None:
        db.close()


def ensure_measurement_cache_exists():
    """
    Ensure the measurement_cache table exists in the database.
    """
    db = get_db()

    # Check if measurement_cache table exists
    cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='measurement_cache'")
    if cursor.fetchone() is None:
        # Create the measurement_cache table
        db.execute(
            """
        CREATE TABLE IF NOT EXISTS measurement_cache (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          type TEXT NOT NULL,
          frequency INTEGER NOT NULL,
          power REAL NOT NULL,
          created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(type, frequency)
        )
        """
        )
        db.commit()


def ensure_hat_type_column_exists():
    """
    Ensure the hat_type column exists in the test_result table.
    This is a migration for existing databases.
    """
    db = get_db()

    # Check if hat_type column exists in test_result table
    try:
        db.execute("SELECT hat_type FROM test_result LIMIT 1")
    except Exception:
        # Add hat_type column with default value 'classic'
        db.execute("ALTER TABLE test_result ADD COLUMN hat_type TEXT DEFAULT 'classic'")
        db.commit()
        logger.info("Added hat_type column to test_result table")


def ensure_settings_table_exists():
    """Create settings table and seed defaults for billboard config."""
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    db.commit()
    defaults = {
        "billboard_show_classic": "1",
        "billboard_show_hybrid": "1",
        "billboard_show_spectrum": "1",
        "billboard_show_votes": "0",
        "billboard_vote_show_labels": "0",
    }
    for k, v in defaults.items():
        db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
    db.commit()


def ensure_photo_path_column_exists():
    """Ensure photo_path column exists on contestant (migration for existing DBs)."""
    db = get_db()
    if not db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='contestant'").fetchone():
        return  # table not created yet — schema.sql will include the column
    try:
        db.execute("SELECT photo_path FROM contestant LIMIT 1")
    except Exception:
        db.execute("ALTER TABLE contestant ADD COLUMN photo_path TEXT")
        db.commit()


def ensure_votes_table_exists():
    """Ensure the votes table exists."""
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contestant_id INTEGER NOT NULL,
            created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (contestant_id) REFERENCES contestant (id)
        )
    """)
    db.commit()


def ensure_class_table_exists():
    """Ensure the class table exists."""
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS class (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            is_team BOOLEAN NOT NULL DEFAULT 0,
            created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()


def ensure_contestant_class_column_exists():
    """Add class_id FK to contestant if missing (migration for existing DBs)."""
    db = get_db()
    if not db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='contestant'").fetchone():
        return
    try:
        db.execute("SELECT class_id FROM contestant LIMIT 1")
    except Exception:
        db.execute("ALTER TABLE contestant ADD COLUMN class_id INTEGER REFERENCES class(id)")
        db.commit()


def ensure_indexes_exist():
    """Create query-optimization indexes if missing."""
    db = get_db()
    stmts = [
        "CREATE INDEX IF NOT EXISTS idx_test_result_contestant ON test_result(contestant_id)",
        "CREATE INDEX IF NOT EXISTS idx_test_result_best       ON test_result(is_best_score)",
        "CREATE INDEX IF NOT EXISTS idx_votes_contestant       ON votes(contestant_id)",
    ]
    # idx_contestant_class only if column exists
    try:
        db.execute("SELECT class_id FROM contestant LIMIT 1")
        stmts.append("CREATE INDEX IF NOT EXISTS idx_contestant_class ON contestant(class_id)")
    except Exception:
        pass
    for stmt in stmts:
        db.execute(stmt)
    db.commit()


def init_db():
    """
    Initialize the database with schema.
    """
    db = get_db()

    schema_path = Path(__file__).parent / "schema.sql"
    with schema_path.open("r") as f:
        db.executescript(f.read())

    ensure_measurement_cache_exists()
    ensure_hat_type_column_exists()
    ensure_photo_path_column_exists()
    ensure_votes_table_exists()
    ensure_settings_table_exists()
    ensure_class_table_exists()
    ensure_contestant_class_column_exists()
    ensure_indexes_exist()


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo("Initialized the database.")
