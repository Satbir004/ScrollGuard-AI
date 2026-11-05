"""
Distraction state machine.

Consumes FrameMetadata every frame and decides when to fire alerts.
Pure Python — no Qt, no audio, no DB. Fully unit-testable.

States:
    NO_PHONE              — nothing on screen
    PHONE_DETECTED        — phone just appeared
    PHONE_ON_DESK         — phone visible but stationary, no hand nearby
    HAND_APPROACHING      — hand near phone (prox > hand_proximity_threshold)
    PHONE_PICKED_UP       — high proximity + phone moving
    POSSIBLE_PHONE_USE    — picked up and sustained
    DISTRACTION_CONFIRMED — held for confirm_distraction_min_seconds → 🚨

Time rules (seconds, from DetectionConfig):
    phone_visible_min_seconds     → PHONE_DETECTED → PHONE_ON_DESK
    possible_use_min_seconds      → PHONE_PICKED_UP → POSSIBLE_PHONE_USE
    confirm_distraction_min_seconds → POSSIBLE_PHONE_USE → DISTRACTION_CONFIRMED
    phone_absent_reset_seconds    → any → NO_PHONE
    release_min_seconds           → DISTRACTION_CONFIRMED → PHONE_ON_DESK

Emitted events (via callback):
    on_enter(state)               → state changed
    on_distraction_start()        → entered DISTRACTION_CONFIRMED
    on_distraction_end()          → left DISTRACTION_CONFIRMED
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional

from .detection_config import DetectionConfig

logger = logging.getLogger(__name__)


class DistractionState(str, Enum):
    NO_PHONE = "NO_PHONE"
    PHONE_DETECTED = "PHONE_DETECTED"
    PHONE_ON_DESK = "PHONE_ON_DESK"
    HAND_APPROACHING = "HAND_APPROACHING"
    PHONE_PICKED_UP = "PHONE_PICKED_UP"
    POSSIBLE_PHONE_USE = "POSSIBLE_PHONE_USE"
    DISTRACTION_CONFIRMED = "DISTRACTION_CONFIRMED"


STATE_COLORS = {
    DistractionState.NO_PHONE:              (120, 120, 120),
    DistractionState.PHONE_DETECTED:        (0, 220, 255),
    DistractionState.PHONE_ON_DESK:         (100, 200, 100),
    DistractionState.HAND_APPROACHING:      (0, 200, 255),
    DistractionState.PHONE_PICKED_UP:       (0, 140, 255),
    DistractionState.POSSIBLE_PHONE_USE:    (0, 80, 255),
    DistractionState.DISTRACTION_CONFIRMED: (0, 0, 255),
}


@dataclass
class AnalyzerInput:
    """Subset of FrameMetadata the analyzer cares about."""
    timestamp: float
    phone_visible: bool
    phone_confidence: float
    phone_center: Optional[tuple[float, float]]
    proximity: float
    hands_visible: int


@dataclass
class AnalyzerOutput:
    state: DistractionState
    state_changed: bool
    distraction_started: bool
    distraction_ended: bool
    state_elapsed_seconds: float
    confidence: float
    reason: str


@dataclass
class AnalyzerCallbacks:
    on_enter: Optional[Callable[[DistractionState], None]] = None
    on_distraction_start: Optional[Callable[[], None]] = None
    on_distraction_end: Optional[Callable[[], None]] = None


class DistractionAnalyzer:
    def __init__(
        self,
        config: Optional[DetectionConfig] = None,
        callbacks: Optional[AnalyzerCallbacks] = None,
    ):
        self.config = config or DetectionConfig.from_file()
        self.callbacks = callbacks or AnalyzerCallbacks()

        self.state = DistractionState.NO_PHONE
        self._state_entered_at: float = 0.0
        self._first_phone_seen_at: Optional[float] = None
        self._last_phone_absent_at: Optional[float] = None
        self._last_phone_center: Optional[tuple[float, float]] = None
        self._last_center_at: Optional[float] = None
        self._movement_px_per_frame: float = 0.0

        # Sub-timers
        self._near_started_at: Optional[float] = None
        self._picked_up_started_at: Optional[float] = None
        self._confirmed_started_at: Optional[float] = None
        self._release_started_at: Optional[float] = None

        self._confidence: float = 0.0
        self._last_reason: str = "initial"

    # ---- Public API ----

    def reset(self) -> None:
        self.state = DistractionState.NO_PHONE
        self._state_entered_at = 0.0
        self._first_phone_seen_at = None
        self._last_phone_absent_at = None
        self._last_phone_center = None
        self._last_center_at = None
        self._movement_px_per_frame = 0.0
        self._near_started_at = None
        self._picked_up_started_at = None
        self._confirmed_started_at = None
        self._release_started_at = None
        self._confidence = 0.0
        self._last_reason = "reset"

    def process(self, inp: AnalyzerInput) -> AnalyzerOutput:
        old_state = self.state
        self._last_reason = ""

        # Compute movement
        if inp.phone_center and self._last_phone_center and self._last_center_at:
            dt = max(inp.timestamp - self._last_center_at, 1e-6)
            dx = inp.phone_center[0] - self._last_phone_center[0]
            dy = inp.phone_center[1] - self._last_phone_center[1]
            dist = (dx * dx + dy * dy) ** 0.5
            # Normalize to per-frame at 30fps so thresholds are stable
            self._movement_px_per_frame = dist / (dt * 30.0)
        else:
            self._movement_px_per_frame *= 0.7  # decay

        if inp.phone_center:
            self._last_phone_center = inp.phone_center
            self._last_center_at = inp.timestamp

        # ---------------- State transitions ----------------
        if not inp.phone_visible:
            self._handle_no_phone(inp)
        else:
            self._handle_phone_visible(inp)

        # Fire callbacks if state changed
        state_changed = self.state != old_state
        if state_changed:
            self._state_entered_at = inp.timestamp
            logger.info(
                "State: %s → %s (%s)",
                old_state.value, self.state.value, self._last_reason,
            )
            if self.callbacks.on_enter:
                try:
                    self.callbacks.on_enter(self.state)
                except Exception:
                    logger.exception("on_enter callback failed")

            # Distraction started?
            if self.state == DistractionState.DISTRACTION_CONFIRMED:
                self._confidence = max(inp.phone_confidence, 0.5)
                if self.callbacks.on_distraction_start:
                    try:
                        self.callbacks.on_distraction_start()
                    except Exception:
                        logger.exception("on_distraction_start callback failed")

            # Distraction ended?
            if old_state == DistractionState.DISTRACTION_CONFIRMED and self.state != DistractionState.DISTRACTION_CONFIRMED:
                if self.callbacks.on_distraction_end:
                    try:
                        self.callbacks.on_distraction_end()
                    except Exception:
                        logger.exception("on_distraction_end callback failed")

        return AnalyzerOutput(
            state=self.state,
            state_changed=state_changed,
            distraction_started=(
                state_changed and self.state == DistractionState.DISTRACTION_CONFIRMED
            ),
            distraction_ended=(
                state_changed
                and old_state == DistractionState.DISTRACTION_CONFIRMED
                and self.state != DistractionState.DISTRACTION_CONFIRMED
            ),
            state_elapsed_seconds=inp.timestamp - self._state_entered_at,
            confidence=self._confidence,
            reason=self._last_reason,
        )

    # ---- Internals ----

    def _handle_no_phone(self, inp: AnalyzerInput) -> None:
        if self._last_phone_absent_at is None:
            self._last_phone_absent_at = inp.timestamp
        absent_for = inp.timestamp - self._last_phone_absent_at

        if absent_for >= self.config.phone_absent_reset_seconds:
            self._transition(DistractionState.NO_PHONE, "phone absent for reset period")
            self._first_phone_seen_at = None
            self._near_started_at = None
            self._picked_up_started_at = None
            self._confirmed_started_at = None
            self._release_started_at = None
            self._confidence = 0.0

    def _handle_phone_visible(self, inp: AnalyzerInput) -> None:
        self._last_phone_absent_at = None

        if self._first_phone_seen_at is None:
            self._first_phone_seen_at = inp.timestamp

        visible_for = inp.timestamp - self._first_phone_seen_at

        # Always reset release timer if proximity is high again
        if inp.proximity >= self.config.hand_proximity_threshold:
            self._release_started_at = None
        # Track release duration when in a "held" state
        if self.state in (
            DistractionState.POSSIBLE_PHONE_USE,
            DistractionState.DISTRACTION_CONFIRMED,
        ):
            if inp.proximity < self.config.release_proximity_threshold:
                if self._release_started_at is None:
                    self._release_started_at = inp.timestamp
                release_for = inp.timestamp - self._release_started_at
                if release_for >= self.config.release_min_seconds:
                    self._transition(
                        DistractionState.PHONE_ON_DESK,
                        f"released for {release_for:.1f}s",
                    )
                    self._near_started_at = None
                    self._picked_up_started_at = None
                    self._confirmed_started_at = None
                    return
            else:
                self._release_started_at = None

        # STATE: NO_PHONE → PHONE_DETECTED
        if self.state == DistractionState.NO_PHONE:
            self._transition(DistractionState.PHONE_DETECTED, "phone appeared")
            return

        # STATE: PHONE_DETECTED → PHONE_ON_DESK
        if self.state == DistractionState.PHONE_DETECTED:
            if visible_for >= self.config.phone_visible_min_seconds:
                self._transition(DistractionState.PHONE_ON_DESK, "phone stable")
            return

        # STATE: PHONE_ON_DESK → HAND_APPROACHING or PHONE_PICKED_UP
        if self.state == DistractionState.PHONE_ON_DESK:
            if inp.proximity >= self.config.hand_proximity_threshold:
                if self._near_started_at is None:
                    self._near_started_at = inp.timestamp
                # Immediate promote if very close AND moving (picked up)
                if (inp.proximity >= 0.7
                        and self._movement_px_per_frame >= self.config.pickup_movement_px_per_frame):
                    self._transition(DistractionState.PHONE_PICKED_UP, "picked up fast")
                else:
                    self._transition(DistractionState.HAND_APPROACHING, "hand near phone")
            return

        # STATE: HAND_APPROACHING → PHONE_PICKED_UP (or back to DESK)
        if self.state == DistractionState.HAND_APPROACHING:
            if inp.proximity < self.config.pickup_proximity_threshold:
                # Hand moved away
                if self._near_started_at and inp.timestamp - self._near_started_at > 1.0:
                    self._transition(DistractionState.PHONE_ON_DESK, "hand moved away")
                    self._near_started_at = None
                return
            if inp.proximity >= self.config.hand_proximity_threshold:
                if self._picked_up_started_at is None:
                    self._picked_up_started_at = inp.timestamp
                # Picked up if: high proximity sustained OR high movement
                if (self._movement_px_per_frame >= self.config.pickup_movement_px_per_frame
                        or (inp.timestamp - self._near_started_at or inp.timestamp) > 0.5):
                    self._transition(DistractionState.PHONE_PICKED_UP, "picked up sustained")
            return

        # STATE: PHONE_PICKED_UP → POSSIBLE_PHONE_USE
        if self.state == DistractionState.PHONE_PICKED_UP:
            if self._picked_up_started_at is None:
                self._picked_up_started_at = inp.timestamp
            held_for = inp.timestamp - self._picked_up_started_at
            if inp.proximity >= self.config.hand_proximity_threshold:
                if held_for >= self.config.possible_use_min_seconds:
                    self._transition(DistractionState.POSSIBLE_PHONE_USE, "held")
            else:
                # Let the release logic above handle it
                pass
            return

        # STATE: POSSIBLE_PHONE_USE → DISTRACTION_CONFIRMED
        if self.state == DistractionState.POSSIBLE_PHONE_USE:
            if self._confirmed_started_at is None:
                self._confirmed_started_at = inp.timestamp
            held_for = inp.timestamp - self._confirmed_started_at
            if inp.proximity >= self.config.hand_proximity_threshold:
                if held_for >= self.config.confirm_distraction_min_seconds:
                    self._transition(
                        DistractionState.DISTRACTION_CONFIRMED,
                        "held long enough",
                    )
            return

        # STATE: DISTRACTION_CONFIRMED — release logic handles exit
        if self.state == DistractionState.DISTRACTION_CONFIRMED:
            # Stays here until release detected above
            pass

    def _transition(self, new_state: DistractionState, reason: str) -> None:
        if self.state == new_state:
            return
        self.state = new_state
        self._last_reason = reason