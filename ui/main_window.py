"""
Main application window. Holds the sidebar + stacked pages.
Handles routing, system tray, and global pause hotkey.
"""
from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QStackedWidget, QSystemTrayIcon,
    QMenu, QApplication, QMessageBox,
)

from ui.components.sidebar import Sidebar
from ui.pages.dashboard import DashboardPage
from ui.pages.monitoring import MonitoringPage
from ui.pages.focus import FocusPage
from ui.pages.analytics import AnalyticsPage
from ui.pages.history import HistoryPage
from ui.pages.alerts import AlertsPage
from ui.pages.settings import SettingsPage

logger = logging.getLogger(__name__)

PLACEHOLDER_TITLES = {}

class MainWindow(QMainWindow):
    pause_toggled = Signal(bool)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ScrollGuard AI")
        self.resize(1280, 800)
        self.setMinimumSize(1024, 700)

        # Central layout: sidebar | page stack
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.page_changed.connect(self._switch_page)
        layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, stretch=1)

        self.setCentralWidget(central)

        # Pages
        self.pages: dict[str, QWidget] = {}
        self._add_page("dashboard", DashboardPage())
        # Live Monitoring is its own page (Phase 7.5)
        self.monitoring_page = MonitoringPage()
        self.monitoring_page.distraction_recorded.connect(self._refresh_dashboard)
        self._add_page("monitoring", self.monitoring_page)

        # Focus Session page (Phase 7.6)
        self.focus_page = FocusPage()
        self._add_page("focus", self.focus_page)
        self._add_page("analytics", AnalyticsPage())
        self._add_page("history", HistoryPage())
        self._add_page("alerts", AlertsPage())
        self._add_page("settings", SettingsPage())

        self.monitoring_page.distraction_started.connect(
            self.focus_page.on_distraction_started
        )
        self.monitoring_page.distraction_ended.connect(
            self.focus_page.on_distraction_ended
        )
        # Also refresh dashboard when a distraction is recorded
        self.monitoring_page.distraction_recorded.connect(
            self.focus_page._refresh_today_summary
        )

        # Remaining pages still placeholders
        for key, (title, sub) in PLACEHOLDER_TITLES.items():
            self._add_page(key, PlaceholderPage(title, sub))

        # Start on dashboard
        self.sidebar.set_active("dashboard")
        self._switch_page("dashboard")

        # System tray
        self._setup_tray()

        # Global pause hotkey (Ctrl+Shift+P)
        self._setup_hotkey()

    # ---- Page routing ----

    def _add_page(self, key: str, page: QWidget) -> None:
        self.pages[key] = page
        self.stack.addWidget(page)

    def _switch_page(self, key: str) -> None:
        page = self.pages.get(key)
        if page:
            self.stack.setCurrentWidget(page)
            self.sidebar.set_active(key)

    def _refresh_dashboard(self) -> None:
        """Refresh dashboard stats after a new distraction is recorded."""
        dash = self.pages.get("dashboard")
        if dash and hasattr(dash, "_refresh"):
            dash._refresh()

    def _toggle_pause(self) -> None:
        paused = getattr(self, "_paused", False)
        paused = not paused
        self._paused = paused
        self.pause_toggled.emit(paused)
        # Mirror the pause into the monitoring page
        if self.monitoring_page is not None:
            if paused and not self.monitoring_page._paused:
                self.monitoring_page._toggle_pause()
            elif not paused and self.monitoring_page._paused:
                self.monitoring_page._toggle_pause()
        if hasattr(self, "tray_icon"):
            self.tray_icon.setToolTip(
                "ScrollGuard AI — " + ("PAUSED" if paused else "Monitoring")
            )
        logger.info("Monitoring %s", "PAUSED" if paused else "RESUMED")

    # ---- System tray ----

    def _setup_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("System tray not available on this system")
            return

        from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
        # Simple colored square as fallback icon
        pm = QPixmap(32, 32)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setBrush(QColor("#6366F1"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(4, 4, 24, 24, 6, 6)
        p.end()

        self.tray_icon = QSystemTrayIcon(QIcon(pm), self)
        self.tray_icon.setToolTip("ScrollGuard AI — Monitoring")

        menu = QMenu()
        show_action = QAction("Show window", self)
        show_action.triggered.connect(self._show_from_tray)
        menu.addAction(show_action)

        pause_action = QAction("Pause / Resume (Ctrl+Shift+P)", self)
        pause_action.triggered.connect(self._toggle_pause)
        menu.addAction(pause_action)

        menu.addSeparator()

        quit_action = QAction("Quit ScrollGuard", self)
        quit_action.triggered.connect(self._quit_app)
        menu.addAction(quit_action)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._show_from_tray()

    def _show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    # ---- Global pause hotkey ----

    def _setup_hotkey(self) -> None:
        # Note: QShortcut only works when this window has focus.
        # True *global* hotkeys require a separate library (keyboard/pynput);
        # for now this works while the app window is focused — good enough
        # for Phase 7, will upgrade in Phase 8.
        self._pause_shortcut = QShortcut(QKeySequence("Ctrl+Shift+P"), self)
        self._pause_shortcut.activated.connect(self._toggle_pause)

    def _toggle_pause(self) -> None:
        paused = getattr(self, "_paused", False)
        paused = not paused
        self._paused = paused
        self.pause_toggled.emit(paused)
        if hasattr(self, "tray_icon"):
            self.tray_icon.setToolTip(
                "ScrollGuard AI — " + ("PAUSED" if paused else "Monitoring")
            )
        logger.info("Monitoring %s", "PAUSED" if paused else "RESUMED")

    # ---- Close → minimize to tray ----

    def closeEvent(self, event: QCloseEvent) -> None:
        if hasattr(self, "tray_icon") and self.tray_icon.isVisible():
            self.hide()
            self.tray_icon.showMessage(
                "ScrollGuard AI",
                "Still monitoring in the background. Right-click the tray icon to quit.",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )
            event.ignore()
        else:
            event.accept()

    def _quit_app(self) -> None:
        if hasattr(self, "monitoring_page") and self.monitoring_page is not None:
            self.monitoring_page.shutdown()
        if hasattr(self, "tray_icon"):
            self.tray_icon.hide()
        QApplication.quit()