"""SQLite connection handling and first-launch initialisation."""
import sqlite3
from pathlib import Path

from flask import current_app, g

from .models import SCHEMA


def connect(path):
    # isolation_level=None -> autocommit; transactions are explicit (BEGIN IMMEDIATE).
    conn = sqlite3.connect(path, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    """Create tables (if missing) and seed sample data on a brand-new database."""
    from database.seed_data import seed  # top-level `database/` package

    path = Path(app.config["DATABASE"])
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(str(path))
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)
        if conn.execute("SELECT COUNT(*) FROM organizers").fetchone()[0] == 0:
            seed(conn, app.config["ORGANIZER_USERNAME"], app.config["ORGANIZER_PASSWORD"])
    finally:
        conn.close()
