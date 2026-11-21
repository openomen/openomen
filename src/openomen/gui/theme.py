"""
Visual system for the OpenOMEN GUI.

Matte black chassis, gunmetal raised areas, etched hairlines and one red.
Chakra Petch (cut-corner letterforms) for numerals, headings and navigation;
Barlow (DIN / road-sign lineage) for everything else. The chamfered corner,
taken from OMEN hardware, marks two things only: live instruments and the
currently selected choice.
"""

import glob
import os

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette

# ---- color tokens
BLACK = "#000000"      # chassis: window background
GUNMETAL = "#16171A"   # raised areas: instrument panels, selected choices
GUNMETAL_2 = "#202126" # tracks, hover
ETCH = "#2C2D32"       # hairlines, outlines, scale ticks
DIM = "#6B6D75"        # tick labels, disabled text
STEEL = "#A2A4AC"      # secondary text
WHITE = "#F2F2F0"      # primary text
RED = "#E4002B"        # fills, active state
AMBER = "#F5A400"      # running warm
GOOD = "#3CCB7F"       # passed checks only

# ---- type
DISPLAY = "Chakra Petch"
BODY = "Barlow"

# point sizes (scale: 9 / 10.5 / 12.5 / 20 / 44)
CAPTION_PT = 9
BODY_PT = 10.5
SECTION_PT = 12.5
TITLE_PT = 20
HERO_PT = 44

CHAMFER = 14  # px cut on the top-left corner of instruments / selected choices

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")


def temp_color(celsius):
    """ White when normal, amber from 70 °C, red from 85 °C. """
    if celsius is None:
        return DIM
    if celsius >= 85:
        return RED
    if celsius >= 70:
        return AMBER
    return WHITE


def qcolor(hex_color, alpha=255):
    c = QColor(hex_color)
    c.setAlpha(alpha)
    return c


def font(family=BODY, point_size=BODY_PT, weight=QFont.Normal):
    f = QFont(family)
    f.setPointSizeF(point_size)
    f.setWeight(weight)
    f.setHintingPreference(QFont.PreferNoHinting)
    return f


def display_font(point_size, weight=QFont.DemiBold):
    return font(DISPLAY, point_size, weight)


def load_fonts():
    for path in glob.glob(os.path.join(FONT_DIR, "*.ttf")):
        QFontDatabase.addApplicationFont(path)


def apply(app):
    load_fonts()
    palette = QPalette()
    for role, color in (
        (QPalette.Window, BLACK), (QPalette.WindowText, WHITE), (QPalette.Base, GUNMETAL),
        (QPalette.AlternateBase, GUNMETAL_2), (QPalette.Text, WHITE), (QPalette.Button, GUNMETAL),
        (QPalette.ButtonText, WHITE), (QPalette.Highlight, RED), (QPalette.HighlightedText, WHITE),
        (QPalette.ToolTipBase, GUNMETAL), (QPalette.ToolTipText, WHITE), (QPalette.PlaceholderText, DIM),
    ):
        palette.setColor(role, QColor(color))
    app.setPalette(palette)
    app.setFont(font())
    app.setStyleSheet(STYLE_SHEET)


STYLE_SHEET = f"""
QWidget {{
    color: {WHITE};
    font-family: "{BODY}";
    font-size: {BODY_PT}pt;
}}
#Chassis {{
    background: {BLACK};
}}
QToolTip {{
    background: {GUNMETAL};
    color: {WHITE};
    border: 1px solid {ETCH};
    padding: 4px 7px;
}}

#TopBar {{
    background: {BLACK};
    border-bottom: 1px solid {ETCH};
}}
#Wordmark {{
    font-family: "{DISPLAY}";
    font-size: 15pt;
    font-weight: 700;
}}
#Version {{
    color: {DIM};
    font-size: {CAPTION_PT}pt;
}}

#Section {{
    font-family: "{DISPLAY}";
    font-size: {SECTION_PT}pt;
    font-weight: 600;
}}
#Steel {{
    color: {STEEL};
}}
#Caption {{
    color: {STEEL};
    font-size: {CAPTION_PT}pt;
}}
#Dim {{
    color: {DIM};
    font-size: {CAPTION_PT}pt;
}}
#Readout {{
    font-family: "{DISPLAY}";
    font-size: 15pt;
    font-weight: 600;
}}
#Strong {{
    font-weight: 600;
}}
#Hairline {{
    background: {ETCH};
    border: none;
}}
#Note {{
    color: {STEEL};
}}

QPushButton {{
    background: transparent;
    border: 1px solid {ETCH};
    border-radius: 0;
    padding: 7px 16px;
    font-weight: 500;
}}
QPushButton:hover {{
    border-color: {STEEL};
}}
QPushButton:focus {{
    border-color: {WHITE};
}}
QPushButton:pressed {{
    background: {GUNMETAL_2};
}}
QPushButton:disabled {{
    color: {DIM};
    border-color: {ETCH};
}}
#RedButton {{
    background: {RED};
    border-color: {RED};
    color: {WHITE};
}}
#RedButton:hover {{
    background: #F5143F;
}}
#RedButton:focus {{
    border-color: {WHITE};
}}

QScrollArea, QScrollArea > QWidget > QWidget {{
    background: transparent;
    border: none;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {ETCH};
    min-height: 40px;
}}
QScrollBar::handle:vertical:hover {{
    background: {DIM};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
}}
QPlainTextEdit {{
    background: {GUNMETAL};
    border: none;
    border-left: 2px solid {AMBER};
    color: {STEEL};
    font-family: "DejaVu Sans Mono", monospace;
    font-size: {CAPTION_PT}pt;
    padding: 6px 10px;
}}
"""
