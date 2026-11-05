"""
Alert orchestration. Wires together:
  - SoundManager (alarm.mp3 loop)
  - VoiceManager (gTTS-generated voice lines)
  - Database (distraction_events + alert_history)

Respects a cooldown so alarms don't spam. Fires on distraction_started
from DistractionAnalyzer, and stops alarm when distraction ends.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from database.repository import AlertRepository, DistractionRepository
from .sound_manager import SoundManager
from .voice_manager import VoiceManager

logger = logging.getLogger(__name__)


class AlertManager:
    def __init__(
        self,
        cooldown_seconds: float = 30.0,
        volume: float = 0.8,
        enable_sound: bool = True,
        enable_voice: bool = True,
        session_id: Optional[int] = None,
    ):
        self.cooldown_seconds = cooldown_seconds
        self.enable_sound = enable_sound
        self.enable_voice = enable_voice
        self.session_id = session_id

        self.sounds = SoundManager(volume=volume)
        self.voice = VoiceManager(volume=volume)

        self._last_fire_at: float = 0.0
        self._current_event_id: Optional[int] = None
        self._initialized = False

    def init(self) -> None:
        if self._initialized:
            return
        if self.enable_sound:
            self.sounds.init()
        if self.enable_voice:
            self.voice.init()
        self._initialized = True

    # ---- Called by state machine callbacks ----

    def on_distraction_started(self, confidence: float = 0.7) -> None:
        """
        Called by state machine when DISTRACTION_CONFIRMED is entered.

        Behavior:
          - ALWAYS records the distraction event + alert row to the DB.
          - Cooldown gates ONLY the audio (alarm.mp3 + voice warning).
          - This gives accurate analytics even when the user picks up the
            phone repeatedly within the cooldown window.
        """
        now = time.time()
        cooldown_active = (
            self.cooldown_seconds > 0
            and (now - self._last_fire_at) < self.cooldown_seconds
        )

        # 1. DB: ALWAYS record the distraction event (before cooldown check)
        try:
            event = DistractionRepository.create(
                session_id=self.session_id,
                confidence=confidence,
                category="phone_use",
                alert_triggered=not cooldown_active,  # 1 if alarm was actually heard
            )
            self._current_event_id = event.id
        except Exception:
            logger.exception("Failed to write distraction event")
            self._current_event_id = None

        # 2. DB: ALWAYS record alert history (marks suppressed ones too)
        try:
            AlertRepository.create(
                reason=(
                    "phone_use_detected" if not cooldown_active
                    else "phone_use_detected_suppressed"
                ),
                level=2 if not cooldown_active else 0,
                event_id=self._current_event_id,
            )
        except Exception:
            logger.exception("Failed to write alert history")

        # 3. Cooldown check for AUDIO only
        if cooldown_active:
            logger.info(
                "Alert audio suppressed (cooldown: %.1fs remaining) — event #%s still logged",
                self.cooldown_seconds - (now - self._last_fire_at),
                self._current_event_id,
            )
            return

        self._last_fire_at = now
        logger.info("🚨 DISTRACTION CONFIRMED — firing alert (audio)")

        if self.enable_sound:
            self.sounds.play_alarm()
        if self.enable_voice:
            self.voice.play_random()

    def on_distraction_ended(self) -> None:
        logger.info("Distraction ended — stopping alarm")

        # Stop audio
        self.sounds.stop_alarm()

        # Close the distraction event in DB
        if self._current_event_id is not None:
            try:
                DistractionRepository.end(self._current_event_id)
            except Exception:
                logger.exception("Failed to close distraction event")
            self._current_event_id = None

    def shutdown(self) -> None:
        self.sounds.stop_alarm()
        self.sounds.shutdown()
        self.voice.shutdown()
        self._initialized = False