""" Widget kit: chamfered instruments, peak-hold scales, core columns, choices, nav. """

from collections import deque

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (QAbstractButton, QFrame, QGridLayout, QHBoxLayout, QLabel, QSizePolicy,
                               QVBoxLayout, QWidget)

from . import theme

PEAK_WINDOW = 80  # samples kept for peak-hold (~2 minutes at 1.5 s)


# ------------------------------------------------------------------ helpers

def label(text="", object_name=None, wrap=False):
    w = QLabel(text)
    if object_name:
        w.setObjectName(object_name)
    w.setWordWrap(wrap)
    return w


def section(text):
    return label(text, "Section")


def hairline():
    line = QFrame()
    line.setObjectName("Hairline")
    line.setFixedHeight(1)
    return line


def vline():
    line = QFrame()
    line.setObjectName("Hairline")
    line.setFixedWidth(1)
    return line


def set_color(widget, hex_color):
    widget.setStyleSheet(f"color: {hex_color};")


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            clear_layout(item.layout())


def chamfer_path(rect, cut=theme.CHAMFER):
    """ Rectangle with the top-left corner cut at 45°. """
    poly = QPolygonF([
        QPointF(rect.left() + cut, rect.top()),
        QPointF(rect.right(), rect.top()),
        QPointF(rect.right(), rect.bottom()),
        QPointF(rect.left(), rect.bottom()),
        QPointF(rect.left(), rect.top() + cut),
    ])
    path = QPainterPath()
    path.addPolygon(poly)
    path.closeSubpath()
    return path


# ------------------------------------------------------------------ chamfered panel

class ChamferPanel(QFrame):
    """ Gunmetal panel with the OMEN cut corner. Reserved for live instruments. """

    def __init__(self, parent=None, margins=(22, 18, 22, 18)):
        super().__init__(parent)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(*margins)
        self.body.setSpacing(12)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillPath(chamfer_path(QRectF(self.rect())), QColor(theme.GUNMETAL))
        # a short red slash along the cut edge
        p.setPen(QPen(QColor(theme.RED), 2))
        p.drawLine(QPointF(1, theme.CHAMFER - 1), QPointF(theme.CHAMFER - 1, 1))


# ------------------------------------------------------------------ peak-hold scale

class ScaleMeter(QWidget):
    """
    Horizontal instrument with one row per reading: name, big numeral, a bar on a
    ticked scale, and a peak-hold marker for the highest value of the last ~2 minutes.
    """

    LABEL_W = 64
    ROW_H = 74

    def __init__(self, minimum, maximum, tick_step, unit, tick_format=str, value_format="{:.0f}",
                 color_fn=None, auto_max_step=None, parent=None):
        super().__init__(parent)
        self.minimum, self.maximum = minimum, maximum
        self.tick_step = tick_step
        self.unit = unit
        self.tick_format = tick_format
        self.value_format = value_format
        self.color_fn = color_fn or (lambda _v: theme.WHITE)
        self.auto_max_step = auto_max_step  # grow the scale in these steps if a value exceeds it
        self.rows = []  # dicts: name, detail, value, history
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.big = theme.display_font(theme.HERO_PT, QFont.DemiBold)
        self.name_font = theme.display_font(11, QFont.DemiBold)
        self.small = theme.font(theme.BODY, theme.CAPTION_PT)
        self.numeral_w = QFontMetricsF(self.big).horizontalAdvance("8888") + 8
        self._resize()

    def _resize(self):
        self.setFixedHeight(max(1, len(self.rows)) * self.ROW_H + 26)

    def set_rows(self, names):
        if [r["name"] for r in self.rows] == list(names):
            return
        self.rows = [{"name": n, "detail": "", "value": None, "history": deque(maxlen=PEAK_WINDOW)}
                     for n in names]
        self._resize()
        self.update()

    def set_value(self, index, value, detail=""):
        row = self.rows[index]
        row["value"] = value
        row["detail"] = detail
        if value is not None:
            row["history"].append(value)
            if self.auto_max_step and value > self.maximum:
                step = self.auto_max_step
                self.maximum = int(-(-value // step) * step)
        self.update()

    def sizeHint(self):
        return QSize(600, self.height())

    def _x(self, value, left, width):
        span = (self.maximum - self.minimum) or 1
        return left + (min(max(value, self.minimum), self.maximum) - self.minimum) / span * width

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        left = self.LABEL_W + self.numeral_w
        width = self.width() - left - 4
        bar_h = 12

        for i, row in enumerate(self.rows):
            top = i * self.ROW_H
            mid = top + self.ROW_H / 2 + 4
            value = row["value"]

            p.setFont(self.name_font)
            p.setPen(QColor(theme.STEEL))
            p.drawText(QRectF(0, top, self.LABEL_W, self.ROW_H), Qt.AlignLeft | Qt.AlignVCenter, row["name"])

            p.setFont(self.big)
            p.setPen(QColor(self.color_fn(value) if value is not None else theme.DIM))
            text = self.value_format.format(value) if value is not None else "–"
            p.drawText(QRectF(self.LABEL_W, top, self.numeral_w - 10, self.ROW_H),
                       Qt.AlignRight | Qt.AlignVCenter, text)

            # track
            track = QRectF(left, mid - bar_h / 2, width, bar_h)
            p.fillRect(track, QColor(theme.GUNMETAL_2))
            # fill with a slanted leading edge
            if value is not None:
                x = self._x(value, left, width)
                if x > left + 2:
                    slant = min(bar_h * 0.6, x - left)
                    fill = QPolygonF([QPointF(left, track.top()), QPointF(x, track.top()),
                                      QPointF(x - slant, track.bottom()), QPointF(left, track.bottom())])
                    p.setPen(Qt.NoPen)
                    p.setBrush(QColor(theme.RED))
                    p.drawPolygon(fill)
            # peak hold
            if row["history"]:
                peak = max(row["history"])
                px = self._x(peak, left, width)
                p.setPen(QPen(QColor(theme.WHITE), 2))
                p.drawLine(QPointF(px, track.top() - 6), QPointF(px, track.bottom() + 2))
                p.setFont(self.small)
                p.setPen(QColor(theme.STEEL))
                peak_text = f"peak {self.value_format.format(peak)}"
                tw = QFontMetricsF(self.small).horizontalAdvance(peak_text)
                tx = min(max(px - tw / 2, left), left + width - tw)
                p.drawText(QPointF(tx, track.top() - 10), peak_text)
            if row["detail"]:
                p.setFont(self.small)
                p.setPen(QColor(theme.DIM))
                p.drawText(QRectF(left, track.bottom() + 4, width, 16), Qt.AlignRight | Qt.AlignTop,
                           row["detail"])

        # scale ticks under the last row
        base = len(self.rows) * self.ROW_H + 2
        p.setFont(self.small)
        tick = self.minimum
        while tick <= self.maximum + 1e-9:
            x = self._x(tick, left, width)
            p.setPen(QPen(QColor(theme.ETCH), 1))
            p.drawLine(QPointF(x, base - 6), QPointF(x, base))
            p.setPen(QColor(theme.DIM))
            text = self.tick_format(tick)
            tw = QFontMetricsF(self.small).horizontalAdvance(text)
            p.drawText(QPointF(min(max(x - tw / 2, left), left + width - tw), base + 16), text)
            tick += self.tick_step
        p.setPen(QColor(theme.DIM))
        p.drawText(QRectF(0, base, left - 12, 20), Qt.AlignRight | Qt.AlignVCenter, self.unit)


# ------------------------------------------------------------------ bars

class Meter(QWidget):
    """ Flat 4 px usage bar (0-100). """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.value = 0.0
        self.setFixedHeight(4)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_value(self, value):
        self.value = max(0.0, min(100.0, float(value or 0)))
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        r = QRectF(self.rect())
        p.fillRect(r, QColor(theme.GUNMETAL_2))
        if self.value > 0:
            p.fillRect(QRectF(r.left(), r.top(), max(2, r.width() * self.value / 100), r.height()),
                       QColor(theme.RED))


class CoreColumns(QWidget):
    """ One vertical column per CPU thread, filled from the bottom by its load. """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cores = []
        self.setFixedHeight(96)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.small = theme.font(theme.BODY, 8)

    def set_cores(self, cores):
        self.cores = cores or []
        self.update()
        self.setToolTip("\n".join(
            f"Thread {c['cpu']}: {c['usage']:.0f}%" + (f", {c['freq_mhz'] / 1000:.2f} GHz" if c.get("freq_mhz") else "")
            for c in self.cores))

    def paintEvent(self, _event):
        if not self.cores:
            return
        p = QPainter(self)
        n = len(self.cores)
        gap = 4
        col_w = (self.width() - gap * (n - 1)) / n
        area_h = self.height() - 18
        p.setFont(self.small)
        for i, core in enumerate(self.cores):
            x = i * (col_w + gap)
            p.fillRect(QRectF(x, 0, col_w, area_h), QColor(theme.GUNMETAL_2))
            h = area_h * core["usage"] / 100
            if h >= 1:
                p.fillRect(QRectF(x, area_h - h, col_w, h), QColor(theme.RED))
            p.setPen(QColor(theme.DIM))
            p.drawText(QRectF(x, area_h + 2, col_w, 16), Qt.AlignHCenter | Qt.AlignTop, str(core["cpu"]))


# ------------------------------------------------------------------ keyboard focus

KEYBOARD_REASONS = (Qt.TabFocusReason, Qt.BacktabFocusReason, Qt.ShortcutFocusReason)


class KeyboardFocusMixin:
    """ Draw focus indicators only when focus arrived from the keyboard, not from a click or startup. """

    _keyboard_focus = False

    def focusInEvent(self, event):
        self._keyboard_focus = event.reason() in KEYBOARD_REASONS
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self._keyboard_focus = False
        super().focusOutEvent(event)

    def show_focus(self):
        return self.hasFocus() and self._keyboard_focus


# ------------------------------------------------------------------ choices

class ChoiceBlock(KeyboardFocusMixin, QAbstractButton):
    """
    A selectable option (profile, fan mode). The selected one gets the chamfered
    gunmetal plate with a red outline; the rest are flat with an etched outline.
    """

    def __init__(self, title, description="", detail="", compact=False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.title = title
        self.description = description
        self.detail = detail
        self.compact = compact
        self.title_font = theme.display_font(11 if compact else 14)
        self.body_font = theme.font()
        self.small = theme.font(theme.BODY, theme.CAPTION_PT)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFixedHeight(40 if compact else 128)

    def sizeHint(self):
        return QSize(QFontMetricsF(self.title_font).horizontalAdvance(self.title) + 40 if self.compact else 240,
                     self.height())

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        cut = 9 if self.compact else theme.CHAMFER
        if self.isChecked():
            path = chamfer_path(r, cut)
            p.fillPath(path, QColor(theme.GUNMETAL))
            p.setPen(QPen(QColor(theme.RED), 1.5))
            p.drawPath(path)
        else:
            p.setPen(QPen(QColor(theme.STEEL if self.show_focus() else theme.ETCH), 1))
            p.drawRect(r)
        if self.show_focus() and self.isChecked():
            p.setPen(QPen(QColor(theme.WHITE), 1, Qt.DotLine))
            p.drawRect(r.adjusted(3, 3, -3, -3))

        enabled_text = QColor(theme.WHITE if self.isChecked() else theme.STEEL)
        if self.compact:
            p.setFont(self.title_font)
            p.setPen(enabled_text)
            p.drawText(r, Qt.AlignCenter, self.title)
            return

        pad = 18
        inner = r.adjusted(pad, 14, -pad, -12)
        p.setFont(self.title_font)
        p.setPen(QColor(theme.WHITE))
        p.drawText(QRectF(inner.left(), inner.top(), inner.width(), 26), Qt.AlignLeft | Qt.AlignVCenter, self.title)
        if self.isChecked():
            p.setFont(self.small)
            p.setPen(QColor(theme.RED))
            p.drawText(QRectF(inner.left(), inner.top(), inner.width(), 26), Qt.AlignRight | Qt.AlignVCenter,
                       "Current")
        p.setFont(self.body_font)
        p.setPen(QColor(theme.STEEL))
        p.drawText(QRectF(inner.left(), inner.top() + 30, inner.width(), 44),
                   Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, self.description)
        if self.detail:
            p.setFont(self.small)
            p.setPen(QColor(theme.DIM))
            p.drawText(QRectF(inner.left(), inner.bottom() - 16, inner.width(), 16),
                       Qt.AlignLeft | Qt.AlignBottom, self.detail)


# ------------------------------------------------------------------ navigation

class NavButton(KeyboardFocusMixin, QAbstractButton):
    """ Top-bar tab: Chakra Petch label, slanted red underline when current. """

    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.setText(text)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.nav_font = theme.display_font(11.5)
        width = QFontMetricsF(self.nav_font).horizontalAdvance(text)
        self.setFixedSize(int(width) + 28, 56)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect())
        p.setFont(self.nav_font)
        color = theme.WHITE if self.isChecked() else (theme.WHITE if self.underMouse() else theme.STEEL)
        p.setPen(QColor(color))
        p.drawText(r, Qt.AlignCenter, self.text())
        if self.isChecked():
            y = r.bottom() - 3
            bar = QPolygonF([QPointF(r.left() + 14, y), QPointF(r.right() - 10, y),
                             QPointF(r.right() - 14, y + 3), QPointF(r.left() + 10, y + 3)])
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(theme.RED))
            p.drawPolygon(bar)
        if self.show_focus():
            p.setPen(QPen(QColor(theme.STEEL), 1, Qt.DotLine))
            p.setBrush(Qt.NoBrush)
            p.drawRect(r.adjusted(4, 12, -4, -12))

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)


class Mark(QWidget):
    """ Small red slanted mark next to the wordmark. """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 18)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.RED))
        p.drawPolygon(QPolygonF([QPointF(6, 0), QPointF(16, 0), QPointF(10, 18), QPointF(0, 18)]))


# ------------------------------------------------------------------ status line

class StatusLine(QWidget):
    """ A row of readings separated by etched vertical hairlines. """

    def __init__(self, names, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(22)
        self.values = {}
        self.subs = {}
        for i, name in enumerate(names):
            if i:
                layout.addWidget(vline())
            col = QVBoxLayout()
            col.setSpacing(1)
            col.addWidget(label(name, "Caption"))
            value = label("–", "Readout")
            sub = label("", "Steel")
            col.addWidget(value)
            col.addWidget(sub)
            layout.addLayout(col)
            self.values[name] = value
            self.subs[name] = sub
        layout.addStretch(1)

    def set(self, name, value, sub=""):
        self.values[name].setText(value)
        self.subs[name].setText(sub)


# ------------------------------------------------------------------ key/value

class KeyValueGrid(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(20)
        self.grid.setVerticalSpacing(8)
        self.grid.setColumnStretch(1, 1)

    def set_rows(self, rows):
        clear_layout(self.grid)
        for i, (key, value) in enumerate(rows):
            v = label(str(value), wrap=True)
            v.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.grid.addWidget(label(key, "Steel"), i, 0, Qt.AlignTop)
            self.grid.addWidget(v, i, 1)


# ------------------------------------------------------------------ keyboard

class KeyboardPreview(QWidget):
    """ Laptop keyboard split into the 4 lighting zones, left to right. """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.colors = ["#000000"] * 4
        self.lit = False
        self.setFixedHeight(170)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_state(self, colors, lit):
        self.colors = colors
        self.lit = lit
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        deck = QRectF(self.rect()).adjusted(0, 0, -1, -1)
        p.fillPath(chamfer_path(deck), QColor(theme.GUNMETAL))
        area = deck.adjusted(20, 20, -20, -20)
        rows = [15, 14, 13, 12, 9]
        gap = 5
        row_h = (area.height() - gap * (len(rows) - 1)) / len(rows)
        zone_w = area.width() / 4
        for r, count in enumerate(rows):
            y = area.top() + r * (row_h + gap)
            widths = [1.0] * count
            if r == len(rows) - 1:
                widths[count // 2] = 5.0  # spacebar
            unit = (area.width() - gap * (count - 1)) / sum(widths)
            x = area.left()
            for w in widths:
                key_w = unit * w
                zone = max(0, min(3, int((x + key_w / 2 - area.left()) // zone_w)))
                self._key(p, QRectF(x, y, key_w, row_h), zone)
                x += key_w + gap

    def _key(self, p, rect, zone):
        p.setPen(Qt.NoPen)
        if self.lit:
            glow = QColor(self.colors[zone])
            glow.setAlpha(45)
            p.setBrush(glow)
            p.drawRect(rect.adjusted(-2, -2, 2, 2))
        p.setBrush(QColor(theme.BLACK))
        p.drawRect(rect)
        p.setPen(QPen(QColor(self.colors[zone]) if self.lit else QColor(theme.ETCH), 1.2))
        p.setBrush(Qt.NoBrush)
        p.drawRect(rect.adjusted(0.6, 0.6, -0.6, -0.6))


class Swatches(QWidget):
    def __init__(self, colors, parent=None):
        super().__init__(parent)
        self.colors = colors
        self.setFixedSize(4 * 18 + 3 * 3, 18)

    def paintEvent(self, _event):
        p = QPainter(self)
        for i, c in enumerate(self.colors):
            p.fillRect(QRectF(i * 21, 0, 18, 18), QColor(c))
            p.setPen(QColor(theme.ETCH))
            p.drawRect(QRectF(i * 21, 0, 17, 17))
