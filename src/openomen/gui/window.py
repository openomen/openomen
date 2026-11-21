from PySide6.QtCore import Qt
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QMainWindow, QStackedWidget, QVBoxLayout, QWidget

from .. import VERSION
from . import theme
from .pages import FansPage, KeyboardPage, OverviewPage, PowerPage, SystemPage
from .poller import StatsPoller
from .widgets import Mark, NavButton, label


class TopBar(QFrame):
    def __init__(self, names, parent=None):
        super().__init__(parent)
        self.setObjectName("TopBar")
        self.setFixedHeight(57)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(0)

        layout.addWidget(Mark(), 0, Qt.AlignVCenter)
        layout.addSpacing(10)
        wordmark = label("OpenOMEN", "Wordmark")
        layout.addWidget(wordmark, 0, Qt.AlignVCenter)
        layout.addSpacing(36)

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for index, name in enumerate(names):
            button = NavButton(name)
            self.group.addButton(button, index)
            layout.addWidget(button, 0, Qt.AlignBottom)
        layout.addStretch(1)
        layout.addWidget(label(f"Version {VERSION}", "Version"), 0, Qt.AlignVCenter)


class MainWindow(QMainWindow):
    def __init__(self, log_handler=None):
        super().__init__()
        self.setWindowTitle("OpenOMEN")
        self.resize(1160, 800)
        self.setMinimumSize(900, 620)

        self.pages = [
            ("Overview", OverviewPage()),
            ("Fans", FansPage()),
            ("Power", PowerPage()),
            ("Keyboard", KeyboardPage()),
            ("System", SystemPage(log_handler)),
        ]

        root = QWidget()
        root.setObjectName("Chassis")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.topbar = TopBar([name for name, _page in self.pages])
        layout.addWidget(self.topbar)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)

        for _name, page in self.pages:
            self.stack.addWidget(page)
        self.topbar.group.idClicked.connect(self.stack.setCurrentIndex)
        self.topbar.group.button(0).setChecked(True)

        self.poller = StatsPoller(self)
        self.poller.updated.connect(self.on_snapshot)
        self.poller.start()

    def show_page(self, name):
        for index, (page_name, _page) in enumerate(self.pages):
            if page_name.lower() == name.lower():
                self.topbar.group.button(index).setChecked(True)
                self.stack.setCurrentIndex(index)

    def on_snapshot(self, snapshot):
        # Every page keeps its peak-hold history up to date, visible or not.
        for _name, page in self.pages:
            page.update_snapshot(snapshot)

    def closeEvent(self, event):
        self.poller.stop()
        super().closeEvent(event)
