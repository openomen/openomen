from PySide6.QtWidgets import QButtonGroup

from ..widgets import ChamferPanel, ChoiceBlock, ScaleMeter, label, section
from .base import Page

MODES = {
    "auto": ("Auto", "The BIOS sets fan speed from temperature. Quiet when the laptop is idle.",
             "openomen fan auto"),
    "max": ("Max", "Both fans run at full speed. Loud, but keeps temperatures down during long loads.",
            "openomen fan max"),
}


def rpm_tick(value):
    return "0" if value == 0 else f"{value / 1000:.0f}k"


class FansPage(Page):
    def __init__(self, parent=None):
        super().__init__(parent)
        panel = ChamferPanel()
        # Scale grows in 1000 rpm steps if a fan spins faster than 6000.
        self.scale = ScaleMeter(0, 6000, 1000, "rpm", tick_format=rpm_tick, auto_max_step=1000)
        self.scale.set_rows(["Fan 1", "Fan 2"])
        panel.body.addWidget(self.scale)
        self.content.addWidget(panel)

        self.gap()
        self.content.addWidget(section("Mode"))
        modes = self.row(16)
        self.blocks = {}
        group = QButtonGroup(self)
        for key, (title, description, command) in MODES.items():
            block = ChoiceBlock(title, description, command)
            block.setEnabled(False)
            group.addButton(block)
            modes.addWidget(block, 1)
            self.blocks[key] = block
        self.read_only_note("Switching fan mode", "openomen fan max")
        self.finish()

    def update_snapshot(self, s):
        fan = s.get("fan") or {"rpm": {}, "mode": "unknown"}
        for i, key in enumerate(("fan1", "fan2")):
            rpm = fan["rpm"].get(key)
            self.scale.set_value(i, rpm, "" if rpm is not None else "Not reported by this laptop")
        for key, block in self.blocks.items():
            block.setChecked(fan["mode"] == key)
            block.update()
