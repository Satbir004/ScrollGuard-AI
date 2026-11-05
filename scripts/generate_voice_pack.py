"""
One-time setup: generate the mp3 warning voice lines using gTTS.

Run once with internet:
    python scripts/generate_voice_pack.py

Creates assets/sounds/voice_01.mp3 ... voice_NN.mp3.
After this, VoiceManager works offline.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from alerts.voice_manager import SOUNDS_DIR, VOICE_LINES


def main():
    SOUNDS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        from gtts import gTTS
    except ImportError:
        print("gTTS not installed. Run: pip install gTTS")
        return 1

    print(f"Generating {len(VOICE_LINES)} voice lines into {SOUNDS_DIR}")
    for i, text in enumerate(VOICE_LINES):
        out = SOUNDS_DIR / f"voice_{i+1:02d}.mp3"
        if out.exists():
            print(f"  [{i+1:02d}] exists → skip")
            continue
        print(f"  [{i+1:02d}] '{text}'")
        try:
            gTTS(text=text, lang="en", slow=False).save(str(out))
        except Exception as e:
            print(f"       FAILED: {e}")
            return 1

    print("Done. All voice lines generated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())