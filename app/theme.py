"""Satu-satunya sumber gaya aplikasi: design tokens, font, dan QSS.

Widget tidak boleh memasang warna/ukuran sendiri; cukup beri objectName atau
property, lalu atur di sini.
"""
from PySide6.QtGui import QColor, QFontDatabase, QPalette

from app.paths import asset

# -- Tokens -------------------------------------------------------------------
BG = "#111315"
SURFACE = "#1A1D20"
BORDER = "#30353B"
TEXT = "#F4F5F6"        # kontras 16:1 di atas BG
TEXT_MUTED = "#A3ABB3"  # kontras 7,6:1 di atas BG
ACCENT = "#F2B33D"      # satu-satunya warna aksen
ACCENT_BGR = (61, 179, 242)  # untuk overlay OpenCV

FONT_FAMILY = "Atkinson Hyperlegible"
FONT_FILES = ["AtkinsonHyperlegible-Regular.ttf", "AtkinsonHyperlegible-Bold.ttf"]

SIZE_HERO = 96
SIZE_HISTORY = 26
SIZE_BODY = 15
SIZE_LABEL = 12

ICON_CHECK = asset("icons", "check.svg").as_posix()
ICON_CHEVRON = asset("icons", "chevron.svg").as_posix()

SPACE = 8          # grid dasar; semua jarak kelipatan ini
RADIUS = 4
SIDEBAR_WIDTH = 400

QSS = f"""
* {{
    font-family: "{FONT_FAMILY}";
    font-size: {SIZE_BODY}px;
    color: {TEXT};
}}
QMainWindow, QWidget#root {{ background: {BG}; }}

QLabel[role="section"] {{
    font-size: {SIZE_LABEL}px;
    font-weight: bold;
    letter-spacing: 1.5px;
    color: {TEXT_MUTED};
}}
QLabel[role="muted"] {{ color: {TEXT_MUTED}; }}
QLabel[role="note"] {{ color: {TEXT_MUTED}; font-size: {SIZE_LABEL + 1}px; }}

QLabel#subtitle {{
    font-size: {SIZE_HERO}px;
    font-weight: bold;
    color: {TEXT};
}}
QLabel#subtitle[unsure="true"] {{ color: {TEXT_MUTED}; font-weight: normal; }}

QLabel#history {{ font-size: {SIZE_HISTORY}px; }}
QLabel#history[empty="true"] {{ color: {TEXT_MUTED}; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}

QFrame#rule {{ background: {BORDER}; max-height: 1px; min-height: 1px; border: none; }}

QPushButton {{
    background: transparent;
    border: 1px solid {BORDER};
    border-radius: {RADIUS}px;
    padding: {SPACE - 2}px {SPACE * 2}px;
}}
QPushButton:hover {{ border-color: {TEXT_MUTED}; }}
QPushButton:pressed {{ background: {SURFACE}; }}
QPushButton:focus {{ border-color: {ACCENT}; }}

QComboBox {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: {RADIUS}px;
    padding: {SPACE - 2}px {SPACE + 4}px;
    min-height: 20px;
}}
QComboBox:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: {SPACE * 4}px; }}
QComboBox::down-arrow {{ image: url("{ICON_CHEVRON}"); width: 12px; height: 12px; }}
QComboBox QAbstractItemView {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    selection-background-color: {BORDER};
    selection-color: {TEXT};
    outline: none;
}}

QCheckBox {{ spacing: {SPACE + 2}px; padding: 2px 0; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {TEXT_MUTED};
    border-radius: 2px;
    background: transparent;
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
    image: url("{ICON_CHECK}");
}}
QCheckBox::indicator:focus {{ border-color: {TEXT}; }}

QSlider::groove:horizontal {{ height: 2px; background: {BORDER}; }}
QSlider::sub-page:horizontal {{ height: 2px; background: {TEXT_MUTED}; }}
QSlider::handle:horizontal {{
    width: 14px; height: 14px; margin: -6px 0;
    border-radius: 7px;
    background: {TEXT};
}}
QSlider::handle:horizontal:focus {{ background: {ACCENT}; }}

QScrollBar:vertical {{ background: transparent; width: 8px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 4px; min-height: 24px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""


def apply(app):
    """Pasang font, palet, dan stylesheet ke QApplication."""
    for name in FONT_FILES:
        QFontDatabase.addApplicationFont(str(asset("fonts", name)))
    app.setStyle("Fusion")
    pal = QPalette()
    for role, color in (
        (QPalette.Window, BG), (QPalette.Base, SURFACE), (QPalette.Button, SURFACE),
        (QPalette.WindowText, TEXT), (QPalette.Text, TEXT), (QPalette.ButtonText, TEXT),
        (QPalette.Highlight, ACCENT), (QPalette.HighlightedText, BG),
        (QPalette.PlaceholderText, TEXT_MUTED),
    ):
        pal.setColor(role, QColor(color))
    app.setPalette(pal)
    app.setStyleSheet(QSS)
