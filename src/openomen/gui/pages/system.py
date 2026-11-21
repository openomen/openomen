import contextlib
import io
import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QPlainTextEdit, QPushButton, QVBoxLayout

from ... import VERSION, cli
from ...core import doctor, system
from .. import theme
from ..poller import run_in_background
from ..widgets import KeyValueGrid, clear_layout, hairline, label, section, set_color
from .base import Page

SECTION_NAMES = {
    "kernel": "Kernel and drivers",
    "fan": "Fan control",
    "thermal": "Temperature sensors",
    "power": "Power modes",
    "gpu": "Graphics",
    "battery": "Battery",
    "rgb": "Keyboard lighting",
}


def build_report():
    """ The same text as `openomen info` + `openomen doctor`, for bug reports. """
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        cli.print_system_info()
        print()
        cli.print_doctor()
    return buffer.getvalue()


def load_system_data():
    return {"info": system.get_system_info(), "doctor": doctor.run_checks()}


class RecentLogHandler(logging.Handler):
    """ Keeps the last distinct warnings from openomen.core for this page. """

    def __init__(self, limit=50):
        super().__init__(logging.WARNING)
        self.limit = limit
        self.messages = []

    def emit(self, record):
        message = record.getMessage()
        if message not in self.messages:
            self.messages.append(message)
            del self.messages[:-self.limit]


class SystemPage(Page):
    def __init__(self, log_handler=None, parent=None):
        super().__init__(parent)
        self.log_handler = log_handler
        self._loaded = False

        top = self.row(12)
        heading = QVBoxLayout()
        heading.setSpacing(2)
        heading.addWidget(section("Compatibility"))
        self.summary = label("Checking your laptop…", "Steel")
        heading.addWidget(self.summary)
        top.addLayout(heading, 1)
        self.refresh_button = QPushButton("Check again")
        self.refresh_button.clicked.connect(self.refresh)
        self.copy_button = QPushButton("Copy report")
        self.copy_button.setObjectName("RedButton")
        self.copy_button.setToolTip("Copies the output of 'openomen info' and 'openomen doctor', "
                                    "ready to paste into a GitHub issue.")
        self.copy_button.clicked.connect(self.copy_report)
        top.addWidget(self.refresh_button, 0, Qt.AlignBottom)
        top.addWidget(self.copy_button, 0, Qt.AlignBottom)
        self.status = label("", "Caption")
        self.status.setVisible(False)
        self.content.addWidget(self.status)

        columns = self.row(48)
        self.checks = QVBoxLayout()
        self.checks.setSpacing(5)
        checks_col = QVBoxLayout()
        checks_col.addLayout(self.checks)
        checks_col.addStretch(1)
        columns.addLayout(checks_col, 3)

        info_col = QVBoxLayout()
        info_col.setSpacing(12)
        info_col.addWidget(section("This laptop"))
        self.info = KeyValueGrid()
        info_col.addWidget(self.info)
        info_col.addStretch(1)
        columns.addLayout(info_col, 2)

        self.log_heading = section("Recent warnings")
        self.content.addWidget(self.log_heading)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(110)
        self.content.addWidget(self.log_view)

        self.gap(10)
        self.content.addWidget(hairline())
        self.content.addWidget(label(f"OpenOMEN {VERSION}, free software under the GPL-3.0. Not affiliated "
                                     "with or endorsed by HP Inc.; OMEN and Victus are HP trademarks.", "Dim",
                                     wrap=True))
        self.finish()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._loaded:
            self._loaded = True
            self.refresh()
        self._update_log()

    def refresh(self):
        self.refresh_button.setEnabled(False)
        self.status.setVisible(False)
        run_in_background(load_system_data, self._on_loaded)

    def _on_loaded(self, data, error):
        self.refresh_button.setEnabled(True)
        if error:
            self.summary.setText(f"The check stopped with an error: {error}")
            return
        result = data["doctor"]
        total = result["passed"] + result["failed"]
        self.summary.setText(f"{result['passed']} of {total} checks passed. Failed checks usually mean a "
                             "feature this laptop or kernel doesn't offer.")
        self._show_checks(result)
        self._show_info(data["info"])
        self._update_log()

    def _show_checks(self, result):
        clear_layout(self.checks)
        current = None
        for check in result["checks"]:
            if check["section"] != current:
                current = check["section"]
                if self.checks.count():
                    self.checks.addSpacing(10)
                self.checks.addWidget(label(SECTION_NAMES.get(current, current), "Strong"))
            row = QHBoxLayout()
            row.setSpacing(10)
            mark = label("✓" if check["ok"] else "✗")
            mark.setFixedWidth(14)
            set_color(mark, theme.GOOD if check["ok"] else theme.RED)
            text = label(check["message"], wrap=True)
            set_color(text, theme.WHITE if check["ok"] else theme.STEEL)
            row.addWidget(mark, 0, Qt.AlignTop)
            row.addWidget(text, 1)
            self.checks.addLayout(row)

    def _show_info(self, info):
        cpu, acpi, fan = info["cpu"], info["acpi"], info["fan"]
        gpus = [g["name"] if g["name"] else f"{g['vendor']} graphics" + (f" ({g['driver']})" if g["driver"] else "")
                for g in info["gpus"]]
        kernel = (info["kernel"] or "Unknown").split(" (")[0].replace("Linux version ", "")
        hp_wmi = {"found": "Loaded", "no_hwmon": "Loaded, without sensors", "missing": "Not found"}
        self.info.set_rows([
            ("Processor", f"{cpu['model'] or 'Unknown'}, {cpu['cores'] or '?'} threads"),
            ("Graphics", "\n".join(gpus) or "None found"),
            ("Linux kernel", kernel),
            ("hp-wmi driver", hp_wmi[info["hp_wmi"]["status"]]),
            ("Power modes", ", ".join(acpi["choices"] or []) or "Not available"),
            ("Fan control", "Available" if fan["hwmon_path"] else "Not available"),
            ("OpenOMEN", VERSION),
        ])

    def _update_log(self):
        messages = self.log_handler.messages if self.log_handler else []
        self.log_heading.setVisible(bool(messages))
        self.log_view.setVisible(bool(messages))
        self.log_view.setPlainText("\n".join(messages))

    def copy_report(self):
        self.copy_button.setEnabled(False)

        def done(text, error):
            self.copy_button.setEnabled(True)
            if error:
                self.status.setText(f"Couldn't build the report: {error}")
                self.status.setVisible(True)
                return
            QApplication.clipboard().setText(text)
            self.status.setText("Report copied. Paste it into your GitHub issue.")
            self.status.setVisible(True)

        run_in_background(build_report, done)
