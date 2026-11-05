"""
ScrollGuard AI — full application entry point (Phase 7).
Boots DB, applies theme, launches MainWindow with system tray.
"""
import logging
import os
import sys
from pathlib import Path

# Silence noisy MediaPipe/absl logs
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("GLOG_minloglevel", "2")

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
for noisy in ("absl", "mediapipe", "PIL", "matplotlib"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from database.db import init_db
from ui.styles.theme import APP_STYLESHEET
from ui.main_window import MainWindow


def main():
    # Init DB first — every page reads from it
    init_db()

    app = QApplication(sys.argv)
    app.setApplicationName("ScrollGuard AI")
    app.setOrganizationName("ScrollGuard")
    app.setStyleSheet(APP_STYLESHEET)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()