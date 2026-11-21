from PySide6.QtWidgets import QButtonGroup, QHBoxLayout

from ...core import power
from ..widgets import ChoiceBlock, clear_layout, label, section
from .base import Page

PROFILES = {
    "gaming": ("Gaming", "Full performance with the fans at max, for games and long heavy loads."),
    "balanced": ("Balanced", "Balanced power with automatic fans. Good for everyday use."),
    "quiet": ("Quiet", "Lower power and automatic fans, so the laptop stays cool and quiet."),
}


def profile_detail(key):
    preferred, fan_mode = power.COMBINED_PROFILES[key]
    return f"Power mode {' or '.join(preferred)}, fans {fan_mode}"


class PowerPage(Page):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.content.addWidget(section("Profile"))
        self.content.addWidget(label("A profile sets the power mode and the fan mode together.", "Steel"))
        cards = self.row(16)
        self.blocks = {}
        group = QButtonGroup(self)
        for key in power.COMBINED_PROFILES:
            title, description = PROFILES.get(key, (key.capitalize(), ""))
            block = ChoiceBlock(title, description, profile_detail(key))
            block.setEnabled(False)
            group.addButton(block)
            cards.addWidget(block, 1)
            self.blocks[key] = block

        self.gap()
        self.content.addWidget(section("Power mode"))
        self.content.addWidget(label("The firmware's own power setting, without touching the fans. "
                                     "Which modes you get depends on the laptop.", "Steel", wrap=True))
        self.acpi_row = QHBoxLayout()
        self.acpi_row.setSpacing(8)
        self.content.addLayout(self.acpi_row)
        self._acpi_state = None

        self.gap(6)
        self.read_only_note("Changing the profile", "openomen power apply gaming")
        self.finish()

    def update_snapshot(self, s):
        pw = s.get("power") or {}
        fan = s.get("fan") or {"mode": "unknown"}
        current = pw.get("current")
        active = power.current_combined_profile(current, fan["mode"])
        for key, block in self.blocks.items():
            block.setChecked(key == active)
            block.update()

        state = (tuple(pw.get("choices") or ()), current)
        if state == self._acpi_state:
            return
        self._acpi_state = state
        clear_layout(self.acpi_row)
        choices = pw.get("choices")
        if not choices:
            self.acpi_row.addWidget(label("This kernel doesn't expose power modes (needs Linux 5.15 or newer).",
                                          "Steel"))
        for choice in choices or []:
            block = ChoiceBlock(choice.capitalize(), compact=True)
            block.setChecked(choice == current)
            block.setEnabled(False)
            block.setFixedWidth(block.sizeHint().width())
            self.acpi_row.addWidget(block)
        self.acpi_row.addStretch(1)
