"""
Environment verification script for ScrollGuard AI.
Run after installing requirements.txt to confirm all critical libraries work.
"""

import sys
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def section(name: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {name}")
    print(f"{'=' * 60}")


def check(label: str, fn) -> bool:
    try:
        result = fn()
        print(f"  [OK] {label}: {result}")
        return True
    except Exception as e:
        print(f"  [FAIL] {label}: {e}")
        traceback.print_exc(limit=2)
        return False


def check_python():
    v = sys.version_info
    if v.major != 3 or v.minor != 12:
        raise RuntimeError(f"Expected Python 3.12, got {v.major}.{v.minor}.{v.micro}")
    return f"Python {v.major}.{v.minor}.{v.micro}"


def check_pyside6():
    from PySide6 import __version__ as pyside_ver
    from PySide6.QtWidgets import QApplication  # noqa: F401
    return f"PySide6 {pyside_ver}"


def check_opencv():
    import cv2
    return f"OpenCV {cv2.__version__}"


def check_numpy():
    import numpy as np
    return f"NumPy {np.__version__}"


def check_yolo():
    import ultralytics
    from ultralytics import YOLO  # noqa: F401
    return f"Ultralytics {ultralytics.__version__}"


def check_torch():
    import torch
    device = "CUDA" if torch.cuda.is_available() else "CPU"
    return f"PyTorch {torch.__version__} (device: {device})"


def check_mediapipe():
    import mediapipe as mp
    return f"MediaPipe {mp.__version__}"


def check_pygame():
    import pygame
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
    ver = pygame.version.ver
    pygame.mixer.quit()
    return f"Pygame {ver} (mixer OK)"


def check_gtts():
    import gtts
    return f"gTTS {gtts.__version__}"


def check_sqlite():
    import sqlite3
    return f"SQLite {sqlite3.sqlite_version}"


def check_webcam():
    import cv2
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        cap.release()
        raise RuntimeError("No webcam at index 0")
    ret, frame = cap.read()
    cap.release()
    if not ret:
        raise RuntimeError("Webcam opened but no frame returned")
    h, w = frame.shape[:2]
    return f"Webcam OK - {w}x{h}"


def check_folders():
    required = [
        "ai_engine", "camera", "alerts", "core", "database",
        "ui", "ui/styles", "ui/components", "ui/pages",
        "assets/sounds", "assets/icons", "data", "tests",
    ]
    missing = [f for f in required if not (PROJECT_ROOT / f).exists()]
    if missing:
        raise RuntimeError(f"Missing folders: {missing}")
    return f"All {len(required)} folders present"


def main():
    print("\n" + "#" * 60)
    print("  ScrollGuard AI - Environment Verification")
    print("#" * 60)

    results = []

    section("Python & Core")
    results.append(check("Python", check_python))
    results.append(check("NumPy", check_numpy))
    results.append(check("SQLite", check_sqlite))

    section("GUI")
    results.append(check("PySide6", check_pyside6))

    section("Computer Vision")
    results.append(check("OpenCV", check_opencv))
    results.append(check("PyTorch", check_torch))
    results.append(check("Ultralytics (YOLO)", check_yolo))
    results.append(check("MediaPipe", check_mediapipe))

    section("Audio")
    results.append(check("Pygame (mixer)", check_pygame))
    results.append(check("gTTS", check_gtts))

    section("Hardware")
    results.append(check("Webcam", check_webcam))

    section("Project Structure")
    results.append(check("Folders", check_folders))

    section("Summary")
    passed = sum(results)
    total = len(results)
    print(f"\n  {passed}/{total} checks passed\n")

    if passed == total:
        print("  Environment READY. Proceed to Phase 2.\n")
        return 0
    else:
        print("  Fix the failures above before proceeding.\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())