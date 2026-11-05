"""
Database connection and schema initialization for ScrollGuard AI.

Uses a single module-level connection with row_factory set to sqlite3.Row
so query results behave like dicts. All timestamps are stored as ISO-8601
strings in UTC for portability.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Optional

# Default DB location: <project_root>/data/scrollguard.db
PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "scrollguard.db"

# Thread lock — SQLite connections aren't thread-safe by default
_lock = threading.Lock()
_connection: Optional[sqlite3.Connection] = None
_db_path: Optional[Path] = None


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ─────────────────────────────────────────────────────────────
-- Study sessions (one row per focus session)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS study_sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      TEXT    NOT NULL,
    ended_at        TEXT,
    planned_minutes INTEGER NOT NULL,
    actual_seconds  INTEGER DEFAULT 0,
    status          TEXT    NOT NULL DEFAULT 'active',  -- active|paused|completed|cancelled
    label           TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_started ON study_sessions(started_at);

-- ─────────────────────────────────────────────────────────────
-- Distraction events (only confirmed phone-use events)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS distraction_events (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id       INTEGER REFERENCES study_sessions(id) ON DELETE SET NULL,
    started_at       TEXT    NOT NULL,
    ended_at         TEXT,
    duration_seconds INTEGER DEFAULT 0,
    category         TEXT    NOT NULL DEFAULT 'phone_use',
    confidence       REAL    NOT NULL DEFAULT 0.0,
    alert_triggered  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_distractions_started ON distraction_events(started_at);
CREATE INDEX IF NOT EXISTS idx_distractions_session ON distraction_events(session_id);

-- ─────────────────────────────────────────────────────────────
-- Alert history (every alarm fired)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alert_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fired_at    TEXT    NOT NULL,
    reason      TEXT    NOT NULL,
    level       INTEGER NOT NULL DEFAULT 1,  -- 1=chime, 2=alarm, 3=voice
    event_id    INTEGER REFERENCES distraction_events(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_alerts_fired ON alert_history(fired_at);

-- ─────────────────────────────────────────────────────────────
-- Productivity records (one row per day, aggregated)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS productivity_records (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    day                 TEXT    NOT NULL UNIQUE,  -- YYYY-MM-DD
    focused_seconds     INTEGER NOT NULL DEFAULT 0,
    distracted_seconds  INTEGER NOT NULL DEFAULT 0,
    distraction_count   INTEGER NOT NULL DEFAULT 0,
    productivity_score  REAL    NOT NULL DEFAULT 0.0
);
CREATE INDEX IF NOT EXISTS idx_productivity_day ON productivity_records(day);

-- ─────────────────────────────────────────────────────────────
-- Daily goals
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS daily_goals (
    day               TEXT    PRIMARY KEY,  -- YYYY-MM-DD
    target_minutes    INTEGER NOT NULL DEFAULT 120,
    achieved_minutes  INTEGER NOT NULL DEFAULT 0
);

-- ─────────────────────────────────────────────────────────────
-- User settings (key-value, JSON-serialized values)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
"""


def init_db(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Initialize (or reuse) the database connection and create schema."""
    global _connection, _db_path

    with _lock:
        if _connection is not None:
            return _connection

        path = Path(db_path) if db_path else DEFAULT_DB_PATH
        path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA_SQL)
        conn.commit()

        _connection = conn
        _db_path = path
        return conn


def get_connection() -> sqlite3.Connection:
    """Get the active connection, initializing it if needed."""
    if _connection is None:
        return init_db()
    return _connection


def close_db() -> None:
    """Close the connection. Useful for tests."""
    global _connection, _db_path
    with _lock:
        if _connection is not None:
            _connection.close()
            _connection = None
            _db_path = None


def reset_db(db_path: Path | str | None = None) -> sqlite3.Connection:
    """For tests: close existing connection and start fresh."""
    close_db()
    return init_db(db_path)