"""
Repository layer — all database reads/writes go through here.
Keeps SQL out of UI code and centralizes transactions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from .db import get_connection
from .models import (
    AlertRecord,
    DailyGoal,
    DistractionEvent,
    ProductivityRecord,
    StudySession,
)


def utc_now_iso() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ─────────────────────────────────────────────────────────────
# Study Sessions
# ─────────────────────────────────────────────────────────────

class SessionRepository:
    @staticmethod
    def create(planned_minutes: int, label: Optional[str] = None) -> StudySession:
        conn = get_connection()
        now = utc_now_iso()
        cur = conn.execute(
            "INSERT INTO study_sessions (started_at, planned_minutes, status, label) "
            "VALUES (?, ?, 'active', ?)",
            (now, planned_minutes, label),
        )
        conn.commit()
        return SessionRepository.get(cur.lastrowid)

    @staticmethod
    def get(session_id: int) -> Optional[StudySession]:
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM study_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return StudySession.from_row(row) if row else None

    @staticmethod
    def end(session_id: int, status: str = "completed") -> Optional[StudySession]:
        conn = get_connection()
        conn.execute(
            "UPDATE study_sessions SET ended_at = ?, status = ? WHERE id = ?",
            (utc_now_iso(), status, session_id),
        )
        conn.commit()
        return SessionRepository.get(session_id)

    @staticmethod
    def add_seconds(session_id: int, seconds: int) -> None:
        conn = get_connection()
        conn.execute(
            "UPDATE study_sessions SET actual_seconds = actual_seconds + ? WHERE id = ?",
            (seconds, session_id),
        )
        conn.commit()

    @staticmethod
    def list_recent(limit: int = 20) -> list[StudySession]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM study_sessions ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [StudySession.from_row(r) for r in rows]


# ─────────────────────────────────────────────────────────────
# Distraction Events
# ─────────────────────────────────────────────────────────────

class DistractionRepository:
    @staticmethod
    def create(
        session_id: Optional[int],
        confidence: float,
        category: str = "phone_use",
        alert_triggered: bool = False,
    ) -> DistractionEvent:
        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO distraction_events "
            "(session_id, started_at, category, confidence, alert_triggered) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, utc_now_iso(), category, confidence, int(alert_triggered)),
        )
        conn.commit()
        return DistractionRepository.get(cur.lastrowid)

    @staticmethod
    def get(event_id: int) -> Optional[DistractionEvent]:
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM distraction_events WHERE id = ?", (event_id,)
        ).fetchone()
        return DistractionEvent.from_row(row) if row else None

    @staticmethod
    def end(event_id: int) -> Optional[DistractionEvent]:
        conn = get_connection()
        now = utc_now_iso()
        conn.execute(
            "UPDATE distraction_events SET ended_at = ? WHERE id = ? AND ended_at IS NULL",
            (now, event_id),
        )
        # Recompute duration
        row = conn.execute(
            "SELECT started_at, ended_at FROM distraction_events WHERE id = ?",
            (event_id,),
        ).fetchone()
        if row and row["ended_at"]:
            start = datetime.fromisoformat(row["started_at"])
            end = datetime.fromisoformat(row["ended_at"])
            duration = int((end - start).total_seconds())
            conn.execute(
                "UPDATE distraction_events SET duration_seconds = ? WHERE id = ?",
                (duration, event_id),
            )
        conn.commit()
        return DistractionRepository.get(event_id)

    @staticmethod
    def list_recent(limit: int = 20) -> list[DistractionEvent]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM distraction_events ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [DistractionEvent.from_row(r) for r in rows]

    @staticmethod
    def total_today() -> int:
        conn = get_connection()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM distraction_events WHERE started_at LIKE ?",
            (f"{today}%",),
        ).fetchone()
        return row["c"] if row else 0


# ─────────────────────────────────────────────────────────────
# Alerts
# ─────────────────────────────────────────────────────────────

class AlertRepository:
    @staticmethod
    def create(reason: str, level: int = 1, event_id: Optional[int] = None) -> AlertRecord:
        conn = get_connection()
        cur = conn.execute(
            "INSERT INTO alert_history (fired_at, reason, level, event_id) "
            "VALUES (?, ?, ?, ?)",
            (utc_now_iso(), reason, level, event_id),
        )
        conn.commit()
        return AlertRepository.get(cur.lastrowid)

    @staticmethod
    def get(alert_id: int) -> Optional[AlertRecord]:
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM alert_history WHERE id = ?", (alert_id,)
        ).fetchone()
        return AlertRecord.from_row(row) if row else None

    @staticmethod
    def last_alert_seconds_ago() -> Optional[float]:
        """How many seconds since the last alert. None if no alerts yet."""
        conn = get_connection()
        row = conn.execute(
            "SELECT fired_at FROM alert_history ORDER BY fired_at DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        last = datetime.fromisoformat(row["fired_at"])
        now = datetime.now(timezone.utc)
        return (now - last).total_seconds()


# ─────────────────────────────────────────────────────────────
# Productivity
# ─────────────────────────────────────────────────────────────

class ProductivityRepository:
    @staticmethod
    def upsert_for_day(record: ProductivityRecord) -> ProductivityRecord:
        conn = get_connection()
        conn.execute(
            """
            INSERT INTO productivity_records
              (day, focused_seconds, distracted_seconds, distraction_count, productivity_score)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(day) DO UPDATE SET
              focused_seconds    = excluded.focused_seconds,
              distracted_seconds = excluded.distracted_seconds,
              distraction_count  = excluded.distraction_count,
              productivity_score = excluded.productivity_score
            """,
            (
                record.day,
                record.focused_seconds,
                record.distracted_seconds,
                record.distraction_count,
                record.productivity_score,
            ),
        )
        conn.commit()
        return ProductivityRepository.get_for_day(record.day)

    @staticmethod
    def get_for_day(day: str) -> Optional[ProductivityRecord]:
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM productivity_records WHERE day = ?", (day,)
        ).fetchone()
        return ProductivityRecord.from_row(row) if row else None

    @staticmethod
    def list_last_days(n: int = 7) -> list[ProductivityRecord]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM productivity_records ORDER BY day DESC LIMIT ?", (n,)
        ).fetchall()
        return [ProductivityRecord.from_row(r) for r in rows]


# ─────────────────────────────────────────────────────────────
# Daily Goals
# ─────────────────────────────────────────────────────────────

class GoalRepository:
    @staticmethod
    def set_goal(day: str, target_minutes: int) -> DailyGoal:
        conn = get_connection()
        conn.execute(
            """
            INSERT INTO daily_goals (day, target_minutes)
            VALUES (?, ?)
            ON CONFLICT(day) DO UPDATE SET target_minutes = excluded.target_minutes
            """,
            (day, target_minutes),
        )
        conn.commit()
        return GoalRepository.get_goal(day)

    @staticmethod
    def get_goal(day: str) -> Optional[DailyGoal]:
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM daily_goals WHERE day = ?", (day,)
        ).fetchone()
        return DailyGoal.from_row(row) if row else None

    @staticmethod
    def update_achieved(day: str, achieved_minutes: int) -> None:
        conn = get_connection()
        conn.execute(
            "UPDATE daily_goals SET achieved_minutes = ? WHERE day = ?",
            (achieved_minutes, day),
        )
        conn.commit()


# ─────────────────────────────────────────────────────────────
# Settings (key-value)
# ─────────────────────────────────────────────────────────────

class SettingsRepository:
    @staticmethod
    def set(key: str, value: str) -> None:
        conn = get_connection()
        conn.execute(
            """
            INSERT INTO user_settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
              value = excluded.value,
              updated_at = excluded.updated_at
            """,
            (key, value, utc_now_iso()),
        )
        conn.commit()

    @staticmethod
    def get(key: str, default: Optional[str] = None) -> Optional[str]:
        conn = get_connection()
        row = conn.execute(
            "SELECT value FROM user_settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    @staticmethod
    def all() -> dict[str, str]:
        conn = get_connection()
        rows = conn.execute("SELECT key, value FROM user_settings").fetchall()
        return {r["key"]: r["value"] for r in rows}