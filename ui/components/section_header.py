"""Small widget for page title + subtitle."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class SectionHeader(QWidget):
    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        t = QLabel(title)
        t.setObjectName("PageTitle")
        layout.addWidget(t)

        if subtitle:
            s = QLabel(subtitle)
            s.setObjectName("PageSubtitle")
            layout.addWidget(s)