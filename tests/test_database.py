"""
Database layer tests. Run with:
    python -m unittest tests.test_database -v
"""

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from database import db
from database.models import ProductivityRecord
from database.repository import (
    AlertRepository,
    DistractionRepository,
    GoalRepository,
    ProductivityRepository,
    SessionRepository,
    SettingsRepository,
)


class DatabaseTestCase(unittest.TestCase):
    def setUp(self):
        self._tmpdir = TemporaryDirectory()
        self.db_path = Path(self._tmpdir.name) / "test.db"
        db.reset_db(self.db_path)

    def tearDown(self):
        db.close_db()
        self._tmpdir.cleanup()

    def test_schema_creates_all_tables(self):
        conn = db.get_connection()
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        tables = {r["name"] for r in rows}
        for expected in {
            "study_sessions",
            "distraction_events",
            "alert_history",
            "productivity_records",
            "daily_goals",
            "user_settings",
        }:
            self.assertIn(expected, tables)

    def test_session_lifecycle(self):
        s = SessionRepository.create(planned_minutes=25, label="Test")
        self.assertIsNotNone(s.id)
        self.assertEqual(s.status, "active")

        SessionRepository.add_seconds(s.id, 60)
        SessionRepository.end(s.id, status="completed")

        s2 = SessionRepository.get(s.id)
        self.assertEqual(s2.status, "completed")
        self.assertEqual(s2.actual_seconds, 60)
        self.assertIsNotNone(s2.ended_at)

    def test_distraction_event_lifecycle(self):
        d = DistractionRepository.create(session_id=None, confidence=0.87)
        self.assertFalse(d.alert_triggered)

        DistractionRepository.end(d.id)
        d2 = DistractionRepository.get(d.id)
        self.assertIsNotNone(d2.ended_at)
        self.assertGreaterEqual(d2.duration_seconds, 0)

    def test_distraction_total_today(self):
        self.assertEqual(DistractionRepository.total_today(), 0)
        DistractionRepository.create(session_id=None, confidence=0.9)
        DistractionRepository.create(session_id=None, confidence=0.8)
        self.assertEqual(DistractionRepository.total_today(), 2)

    def test_alert_cooldown(self):
        # No alerts yet -> None
        self.assertIsNone(AlertRepository.last_alert_seconds_ago())

        AlertRepository.create(reason="phone_use", level=2)
        seconds = AlertRepository.last_alert_seconds_ago()
        self.assertIsNotNone(seconds)
        self.assertLess(seconds, 5.0)

    def test_productivity_upsert(self):
        rec = ProductivityRecord(
            day="2026-01-15",
            focused_seconds=3600,
            distracted_seconds=300,
            distraction_count=3,
            productivity_score=85.0,
        )
        ProductivityRepository.upsert_for_day(rec)

        # Update same day — should not create a duplicate
        rec.distraction_count = 5
        ProductivityRepository.upsert_for_day(rec)

        rows = ProductivityRepository.list_last_days(7)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].distraction_count, 5)

    def test_goal_upsert(self):
        GoalRepository.set_goal("2026-01-15", 120)
        GoalRepository.update_achieved("2026-01-15", 45)
        g = GoalRepository.get_goal("2026-01-15")
        self.assertEqual(g.target_minutes, 120)
        self.assertEqual(g.achieved_minutes, 45)

    def test_settings_roundtrip(self):
        SettingsRepository.set("theme", "dark")
        SettingsRepository.set("volume", "0.8")
        self.assertEqual(SettingsRepository.get("theme"), "dark")
        self.assertEqual(SettingsRepository.get("volume"), "0.8")
        self.assertIsNone(SettingsRepository.get("missing"))
        self.assertEqual(SettingsRepository.get("missing", "default"), "default")

        all_settings = SettingsRepository.all()
        self.assertEqual(all_settings["theme"], "dark")
        self.assertEqual(all_settings["volume"], "0.8")


if __name__ == "__main__":
    unittest.main(verbosity=2)