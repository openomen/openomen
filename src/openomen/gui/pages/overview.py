from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

from ...core import power
from .. import theme
from ..widgets import (ChamferPanel, CoreColumns, Meter, ScaleMeter, StatusLine, clear_layout, hairline, label,
                       section, set_color)
from .base import Page

FAN_MODE = {"max": "Max", "auto": "Auto", "unknown": "Unknown"}


def pick_gpu(gpus):
    """ The GPU to feature on the thermal strip: discrete first, and one that reports a temperature. """
    for vendor in ("NVIDIA", "AMD", "Intel"):
        for g in gpus or []:
            if g["vendor"] == vendor and g["temperature_c"] is not None:
                return g
    return (gpus or [None])[0]


def short_gpu_name(name):
    return name.replace("NVIDIA GeForce ", "").replace("NVIDIA ", "")


def display_gpu_name(g):
    """ The core labels sysfs GPUs generically ('AMDGPU Architecture'); say what they are instead. """
    if g["vendor"] == "AMD":
        return f"AMD Radeon graphics ({g['driver']} driver)" if g["driver"] else "AMD Radeon graphics"
    if g["vendor"] == "Intel":
        return "Intel graphics"
    return g["name"]


def thermal_scale():
    return ScaleMeter(30, 100, 10, "°C", tick_format=lambda t: f"{t:.0f}", value_format="{:.0f}°",
                      color_fn=theme.temp_color)


class GpuRows(QWidget):
    """ Name plus key/value rows for one GPU. """

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.name = label("", "Strong", wrap=True)
        layout.addWidget(self.name)
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(7)
        grid.setColumnStretch(1, 1)
        self.rows = {}
        for i, (key, with_meter) in enumerate((("Temperature", False), ("Load", True),
                                               ("Video memory", True), ("Power draw", False))):
            k = label(key, "Steel")
            k.setFixedWidth(110)  # same column for every GPU, so the meters line up
            meter = Meter() if with_meter else None
            v = label()
            v.setFixedWidth(96)
            v.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            grid.addWidget(k, i, 0)
            if meter:
                grid.addWidget(meter, i, 1, Qt.AlignVCenter)
            grid.addWidget(v, i, 2)
            self.rows[key] = (k, meter, v)
        layout.addLayout(grid)

    def _row(self, key, text, meter_value=None):
        k, meter, v = self.rows[key]
        visible = text is not None
        for w in (k, meter, v):
            if w:
                w.setVisible(visible)
        if visible:
            v.setText(text)
            if meter:
                meter.set_value(meter_value)

    def set_gpu(self, g):
        self.name.setText(display_gpu_name(g))
        t = g["temperature_c"]
        self._row("Temperature", f"{t:.0f} °C" if t is not None else None)
        set_color(self.rows["Temperature"][2], theme.temp_color(t))
        u = g["utilization_pct"]
        self._row("Load", f"{u:.0f}%" if u is not None else None, u)
        used, total = g["vram_used_mib"], g["vram_total_mib"]
        self._row("Video memory", f"{(used or 0) / 1024:.1f} of {total / 1024:.0f} GB" if total else None,
                  (used or 0) / total * 100 if total else 0)
        self._row("Power draw", f"{g['power_w']:.0f} W" if g["power_w"] is not None else None)


class OverviewPage(Page):
    def __init__(self, parent=None):
        super().__init__(parent)

        # The instrument: CPU and GPU temperature on one heat scale with peak hold.
        strip = ChamferPanel()
        self.thermal = thermal_scale()
        self.thermal.set_rows(["CPU", "GPU"])
        strip.body.addWidget(self.thermal)
        self.content.addWidget(strip)

        self.status = StatusLine(["Fans", "Profile", "Power mode", "Keyboard"])
        self.content.addWidget(self.status)
        self.content.addWidget(hairline())

        lower = self.row(40)
        cpu_col = QVBoxLayout()
        cpu_col.setSpacing(10)
        cpu_col.addWidget(section("Processor"))
        self.cpu_name = label("", "Steel")
        cpu_col.addWidget(self.cpu_name)
        self.cores = CoreColumns()
        cpu_col.addWidget(self.cores)
        self.cpu_summary = label("", "Steel")
        cpu_col.addWidget(self.cpu_summary)
        cpu_col.addStretch(1)
        lower.addLayout(cpu_col, 3)

        gpu_col = QVBoxLayout()
        gpu_col.setSpacing(10)
        gpu_col.addWidget(section("Graphics"))
        self.gpu_list = QVBoxLayout()
        self.gpu_list.setSpacing(16)
        gpu_col.addLayout(self.gpu_list)
        gpu_col.addStretch(1)
        self.gpu_rows = []
        self.gpu_count = None
        lower.addLayout(gpu_col, 2)
        self.finish()

    def update_snapshot(self, s):
        cpu = s.get("cpu") or {}
        temp = cpu.get("temperature")
        self.thermal.set_value(0, temp["celsius"] if temp else None,
                               f"{temp['label']}, {temp['driver']}" if temp else "No CPU sensor found")
        gpus = s.get("gpus") or []
        g = pick_gpu(gpus)
        self.thermal.set_value(1, g["temperature_c"] if g else None,
                               short_gpu_name(g["name"]) if g else "No GPU found")

        self.cpu_name.setText(cpu.get("name", ""))
        cores = cpu.get("cores") or []
        self.cores.set_cores(cores)
        if cores:
            avg = sum(c["usage"] for c in cores) / len(cores)
            freqs = [c["freq_mhz"] for c in cores if c.get("freq_mhz")]
            clock = f", clocks {min(freqs) / 1000:.1f} to {max(freqs) / 1000:.1f} GHz" if freqs else ""
            self.cpu_summary.setText(f"{avg:.0f}% average load over {len(cores)} threads{clock}")

        if self.gpu_count != len(gpus):
            self.gpu_count = len(gpus)
            clear_layout(self.gpu_list)
            self.gpu_rows = []
            for i in range(len(gpus)):
                if i:
                    self.gpu_list.addWidget(hairline())
                rows = GpuRows()
                self.gpu_rows.append(rows)
                self.gpu_list.addWidget(rows)
            if not gpus:
                self.gpu_list.addWidget(label("No graphics card was detected.", "Steel"))
        for rows, gpu_data in zip(self.gpu_rows, gpus):
            rows.set_gpu(gpu_data)

        fan = s.get("fan") or {"rpm": {}, "mode": "unknown"}
        rpm = " / ".join(str(v) for v in fan["rpm"].values()) or "–"
        self.status.set("Fans", f"{rpm} rpm" if fan["rpm"] else "–", FAN_MODE[fan["mode"]])

        pw = s.get("power") or {}
        combined = power.current_combined_profile(pw.get("current"), fan["mode"])
        self.status.set("Profile", combined.capitalize() if combined else "Custom",
                        "" if combined else "Doesn't match a preset")
        self.status.set("Power mode", (pw.get("current") or "Unknown").capitalize())

        rgb = s.get("rgb")
        if not rgb or not rgb.get("hardware"):
            self.status.set("Keyboard", "Not available", "No lighting control found")
        elif rgb["enabled"]:
            self.status.set("Keyboard", "On", rgb["active_name"] or "")
        else:
            self.status.set("Keyboard", "Off")
