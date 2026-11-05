"""
Central theme: color palette + QSS stylesheet.
All UI components import colors from here — change once, updates everywhere.
"""

# Palette (from project spec)
BG_PRIMARY      = "#0B1020"
BG_SECONDARY    = "#111827"
CARD_BG         = "#172033"
CARD_BG_HOVER   = "#1E2A44"
ACCENT_PRIMARY  = "#6366F1"
ACCENT_SECONDARY = "#06B6D4"
SUCCESS         = "#22C55E"
WARNING         = "#F59E0B"
DANGER          = "#EF4444"
TEXT_PRIMARY    = "#F8FAFC"
TEXT_SECONDARY  = "#94A3B8"
BORDER          = "#1F2A44"


# Full application stylesheet. Applied to QApplication once at startup.
APP_STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {BG_PRIMARY};
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI", "Inter", "Roboto", sans-serif;
    font-size: 13px;
}}

QToolTip {{
    background-color: {CARD_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    padding: 6px;
    border-radius: 4px;
}}

/* Sidebar */
#Sidebar {{
    background-color: {BG_SECONDARY};
    border-right: 1px solid {BORDER};
}}

#SidebarLogo {{
    color: {TEXT_PRIMARY};
    font-size: 20px;
    font-weight: 700;
    padding: 24px 20px 8px 20px;
}}

#SidebarTagline {{
    color: {TEXT_SECONDARY};
    font-size: 11px;
    padding: 0 20px 24px 20px;
}}

QPushButton#NavButton {{
    background-color: transparent;
    color: {TEXT_SECONDARY};
    text-align: left;
    padding: 10px 20px;
    border: none;
    border-radius: 8px;
    margin: 2px 12px;
    font-size: 13px;
}}

QPushButton#NavButton:hover {{
    background-color: {CARD_BG};
    color: {TEXT_PRIMARY};
}}

QPushButton#NavButton:checked {{
    background-color: {ACCENT_PRIMARY};
    color: {TEXT_PRIMARY};
    font-weight: 600;
}}

/* Cards */
#Card {{
    background-color: {CARD_BG};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}

#CardTitle {{
    color: {TEXT_SECONDARY};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
}}

#CardValue {{
    color: {TEXT_PRIMARY};
    font-size: 26px;
    font-weight: 700;
}}

#CardDelta {{
    color: {SUCCESS};
    font-size: 12px;
    font-weight: 600;
}}

/* Buttons */
QPushButton#PrimaryButton {{
    background-color: {ACCENT_PRIMARY};
    color: {TEXT_PRIMARY};
    border: none;
    border-radius: 8px;
    padding: 10px 18px;
    font-weight: 600;
    font-size: 13px;
}}

QPushButton#PrimaryButton:hover {{
    background-color: #7C7FF7;
}}

QPushButton#PrimaryButton:pressed {{
    background-color: #4F52D9;
}}

QPushButton#SecondaryButton {{
    background-color: transparent;
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 9px 16px;
    font-weight: 500;
    font-size: 13px;
}}

QPushButton#SecondaryButton:hover {{
    background-color: {CARD_BG};
}}

/* Page title */
#PageTitle {{
    color: {TEXT_PRIMARY};
    font-size: 26px;
    font-weight: 700;
}}

#PageSubtitle {{
    color: {TEXT_SECONDARY};
    font-size: 13px;
}}

/* Scroll */
QScrollArea {{
    background: transparent;
    border: none;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background: {ACCENT_PRIMARY};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

/* Focus session pill */
#StatePill {{
    border-radius: 12px;
    padding: 4px 12px;
    font-size: 11px;
    font-weight: 600;
}}
"""