from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from ...core import OpenOMENError, rgb
from .. import theme
from ..widgets import KeyboardPreview, Swatches, clear_layout, hairline, label, section, set_color
from .base import Page


def safe_colors(profile):
    try:
        return ["#" + c for c in rgb.profile_colors(profile)]
    except OpenOMENError:
        return ["#000000"] * rgb.ZONE_COUNT


class ProfileRow(QWidget):
    def __init__(self, profile_id, profile, current, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(16)
        marker = QWidget()
        marker.setFixedSize(3, 34)
        marker.setStyleSheet(f"background: {theme.RED if current else 'transparent'};")
        layout.addWidget(marker)
        text = QVBoxLayout()
        text.setSpacing(1)
        name = label(profile.get("name", profile_id), "Strong")
        text.addWidget(name)
        text.addWidget(label(profile.get("description", "") or f"{profile_id}.json", "Steel", wrap=True))
        layout.addLayout(text, 1)
        if current:
            current_label = label("Current", "Caption")
            set_color(current_label, theme.RED)
            layout.addWidget(current_label, 0, Qt.AlignVCenter)
        layout.addWidget(Swatches(safe_colors(profile)), 0, Qt.AlignVCenter)


class KeyboardPage(Page):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.no_hw = label("", "Note", wrap=True)
        self.content.addWidget(self.no_hw)
        self.keyboard = KeyboardPreview()
        self.content.addWidget(self.keyboard)
        self.state_line = label("", "Steel")
        self.content.addWidget(self.state_line)

        self.gap()
        self.content.addWidget(section("Profiles"))
        self.content.addWidget(label("Saved as JSON files in ~/.config/openomen/rgb/profiles.", "Steel"))
        self.profile_list = QVBoxLayout()
        self.profile_list.setSpacing(0)
        self.content.addLayout(self.profile_list)
        self._state = None

        self.gap(6)
        self.read_only_note("Changing the lighting", "openomen rgb set rainbow")
        self.finish()

    def update_snapshot(self, s):
        status = s.get("rgb")
        if status is None:
            return
        state = (status["enabled"], status["active_profile"], status["hardware"], repr(status["profiles"]))
        if state == self._state:
            return
        self._state = state

        if status["hardware"]:
            self.no_hw.setVisible(False)
        else:
            self.no_hw.setText("OpenOMEN can't find a keyboard lighting control on this laptop. It needs an "
                               "hp-wmi driver that provides rgb_zones, keyboardleds or zone_colors. "
                               "Below is how your saved profile would look.")
            self.no_hw.setVisible(True)

        profiles = status["profiles"]
        current = status["active_profile"]
        active = profiles.get(current) if current else None
        lit = bool(active) and status["enabled"]
        self.keyboard.set_state(safe_colors(active), lit)
        name = status["active_name"]
        self.state_line.setText(f"Lights {'on' if status['enabled'] else 'off'}"
                                + (f", showing {name}" if name and lit else "")
                                + (f" ({status['hardware']})" if status["hardware"] else ""))

        clear_layout(self.profile_list)
        for i, (profile_id, profile) in enumerate(profiles.items()):
            if i:
                self.profile_list.addWidget(hairline())
            self.profile_list.addWidget(ProfileRow(profile_id, profile, profile_id == current))
        if not profiles:
            self.profile_list.addWidget(label("No profiles yet.", "Steel"))
