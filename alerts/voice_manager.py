"""
Voice warning playback. Uses pre-generated mp3 files from gTTS so runtime
stays offline and never blocks on network.

The generation is done once by scripts/generate_voice_pack.py. If a voice
file is missing at play time, we skip it silently (log warning).
"""

from __future__ import annotations

import logging
import random
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
SOUNDS_DIR = PROJECT_ROOT / "assets" / "sounds"

# Warning lines. Keep them short (< 4s), punchy, and non-judgmental.
VOICE_LINES = [
    "Hey! Put the phone down and get back to work.",
    "Your phone is stealing your productivity.",
    "You promised yourself you would study.",
    "Put that phone down and focus.",
    "ScrollGuard here. Stop scrolling.",
    "Study time. Phone down.",
]


class VoiceManager:
    def __init__(
        self,
        volume: float = 0.9,
        sounds_dir: Optional[Path] = None,
        avoid_repeat_count: int = 2,
    ):
        self.sounds_dir = Path(sounds_dir) if sounds_dir else SOUNDS_DIR
        self.volume = max(0.0, min(1.0, volume))
        self._initialized = False
        self._sounds: List = []  # list[pygame.mixer.Sound]
        self._avoid_repeat = avoid_repeat_count
        self._recent: List[int] = []

    def init(self) -> bool:
        if self._initialized:
            return True
        try:
            import pygame
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        except Exception as e:
            logger.error("VoiceManager init failed: %s", e)
            return False

        paths = self._voice_paths()
        loaded = 0
        for p in paths:
            if not p.exists():
                continue
            try:
                s = pygame.mixer.Sound(str(p))
                s.set_volume(self.volume)
                self._sounds.append(s)
                loaded += 1
            except Exception as e:
                logger.warning("Failed to load voice %s: %s", p.name, e)

        self._initialized = True
        logger.info("VoiceManager ready (%d lines loaded)", loaded)
        return loaded > 0

    def _voice_paths(self) -> List[Path]:
        return [self.sounds_dir / f"voice_{i+1:02d}.mp3" for i in range(len(VOICE_LINES))]

    def play_random(self) -> bool:
        if not self._initialized or not self._sounds:
            return False
        try:
            candidates = [
                i for i in range(len(self._sounds)) if i not in self._recent
            ] or list(range(len(self._sounds)))
            idx = random.choice(candidates)
            self._recent.append(idx)
            if len(self._recent) > self._avoid_repeat:
                self._recent.pop(0)
            self._sounds[idx].play()
            logger.info("Voice line played: #%d", idx + 1)
            return True
        except Exception as e:
            logger.error("Voice playback failed: %s", e)
            return False

    def set_volume(self, v: float) -> None:
        self.volume = max(0.0, min(1.0, v))
        for s in self._sounds:
            s.set_volume(self.volume)

    def shutdown(self) -> None:
        self._sounds.clear()
        self._initialized = False