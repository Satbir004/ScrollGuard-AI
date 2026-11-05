"""Dataclass models for ScrollGuard AI database entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class StudySession:
    id: Optional[int] = None
    started_at: str = ""
    ended_at: Optional[str] = None
    planned_minutes: int = 25
    actual_seconds: int = 0
    status: str = "active"  # active|paused|completed|cancelled
    label: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> "StudySession":
        return cls(
            id=row["id"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            planned_minutes=row["planned_minutes"],
            actual_seconds=row["actual_seconds"],
            status=row["status"],
            label=row["label"],
        )


@dataclass
class DistractionEvent:
    id: Optional[int] = None
    session_id: Optional[int] = None
    started_at: str = ""
    ended_at: Optional[str] = None
    duration_seconds: int = 0
    category: str = "phone_use"
    confidence: float = 0.0
    alert_triggered: bool = False

    @classmethod
    def from_row(cls, row) -> "DistractionEvent":
        return cls(
            id=row["id"],
            session_id=row["session_id"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            duration_seconds=row["duration_seconds"],
            category=row["category"],
            confidence=row["confidence"],
            alert_triggered=bool(row["alert_triggered"]),
        )


@dataclass
class AlertRecord:
    id: Optional[int] = None
    fired_at: str = ""
    reason: str = ""
    level: int = 1
    event_id: Optional[int] = None

    @classmethod
    def from_row(cls, row) -> "AlertRecord":
        return cls(
            id=row["id"],
            fired_at=row["fired_at"],
            reason=row["reason"],
            level=row["level"],
            event_id=row["event_id"],
        )


@dataclass
class ProductivityRecord:
    id: Optional[int] = None
    day: str = ""  # YYYY-MM-DD
    focused_seconds: int = 0
    distracted_seconds: int = 0
    distraction_count: int = 0
    productivity_score: float = 0.0

    @classmethod
    def from_row(cls, row) -> "ProductivityRecord":
        return cls(
            id=row["id"],
            day=row["day"],
            focused_seconds=row["focused_seconds"],
            distracted_seconds=row["distracted_seconds"],
            distraction_count=row["distraction_count"],
            productivity_score=row["productivity_score"],
        )


@dataclass
class DailyGoal:
    day: str = ""  # YYYY-MM-DD
    target_minutes: int = 120
    achieved_minutes: int = 0

    @classmethod
    def from_row(cls, row) -> "DailyGoal":
        return cls(
            day=row["day"],
            target_minutes=row["target_minutes"],
            achieved_minutes=row["achieved_minutes"],
        )