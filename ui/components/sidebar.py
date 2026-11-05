"""
Left navigation rail. Emits `page_changed(page_key)` when a button is clicked.
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QButtonGroup,
)


NAV_ITEMS = [
    ("dashboard",  "📊  Dashboard"),
    ("monitoring", "📹  Live Monitoring"),
    ("focus",      "🎯  Focus Session"),
    ("analytics",  "📈  Analytics"),
    ("alerts",     "🔔  Alerts"),
    ("history",    "🗂  History"),
    ("settings",   "⚙️  Settings"),
]


class Sidebar(QWidget):
    page_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 16)
        layout.setSpacing(0)

        logo = QLabel("🛡️  ScrollGuard AI")
        logo.setObjectName("SidebarLogo")
        layout.addWidget(logo)

        tagline = QLabel("Study protection powered by AI")
        tagline.setObjectName("SidebarTagline")
        layout.addWidget(tagline)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}

        for key, label in NAV_ITEMS:
            btn = QPushButton(label)
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.setCursor(btn.cursor())
            btn.clicked.connect(lambda _=False, k=key: self._on_click(k))
            layout.addWidget(btn)
            self._group.addButton(btn)
            self._buttons[key] = btn

        layout.addStretch()

        version = QLabel("v0.7.0 · Phase 7")
        version.setObjectName("SidebarTagline")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)

    def _on_click(self, key: str) -> None:
        self.page_changed.emit(key)

    def set_active(self, key: str) -> None:
        btn = self._buttons.get(key)
        if btn:
            btn.setChecked(True)