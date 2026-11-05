"""
Pygame-based sound playback. Handles alarm looping and short chimes.

All methods are safe to call from the Qt main thread. Pygame mixer is
initialized once at import time with a small buffer for low latency.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
SOUNDS_DIR = PROJECT_ROOT / "assets" / "sounds"


class SoundManager:
    def __init__(self, volume: float = 0.8, sounds_dir: Optional[Path] = None):
        self.sounds_dir = Path(sounds_dir) if sounds_dir else SOUNDS_DIR
        self.volume = max(0.0, min(1.0, volume))
        self._initialized = False
        self._alarm_sound = None
        self._alarm_playing = False
        self._alarm_channel = None

    def init(self) -> bool:
        if self._initialized:
            return True
        try:
            import pygame
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            pygame.mixer.music.set_volume(self.volume)
            self._initialized = True
            logger.info("SoundManager ready (volume=%.2f)", self.volume)
            return True
        except Exception as e:
            logger.error("SoundManager init failed: %s", e)
            return False

    def _load_alarm(self) -> bool:
        if self._alarm_sound is not None:
            return True
        path = self.sounds_dir / "alarm.mp3"
        if not path.exists():
            logger.error("Alarm file not found: %s", path)
            return False
        try:
            import pygame
            self._alarm_sound = pygame.mixer.Sound(str(path))
            self._alarm_sound.set_volume(self.volume)
            return True
        except Exception as e:
            logger.error("Failed to load alarm.mp3: %s", e)
            return False

    def play_alarm(self) -> None:
        """Start the looping alarm. Idempotent while playing."""
        if not self._initialized:
            return
        if self._alarm_playing:
            return
        if not self._load_alarm():
            return
        try:
            self._alarm_channel = self._alarm_sound.play(loops=-1)
            self._alarm_playing = True
            logger.info("🚨 Alarm started")
        except Exception as e:
            logger.error("Failed to play alarm: %s", e)

    def stop_alarm(self) -> None:
        if not self._alarm_playing:
            return
        try:
            if self._alarm_channel is not None:
                self._alarm_channel.stop()
            self._alarm_playing = False
            logger.info("Alarm stopped")
        except Exception as e:
            logger.error("Failed to stop alarm: %s", e)

    def is_alarm_playing(self) -> bool:
        return self._alarm_playing

    def set_volume(self, volume: float) -> None:
        self.volume = max(0.0, min(1.0, volume))
        if self._alarm_sound:
            self._alarm_sound.set_volume(self.volume)

    def shutdown(self) -> None:
        self.stop_alarm()
        try:
            import pygame
            pygame.mixer.quit()
        except Exception:
            pass
        self._initialized = False