from PySide6.QtWidgets import QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from ..widgets import label

MAX_CONTENT_WIDTH = 1180


class Page(QScrollArea):
    """ Scrollable page body; the top bar already names the page, so no title here. """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.NoFrame)
        inner = QWidget()
        inner.setObjectName("Chassis")
        self.setWidget(inner)
        self.content = QVBoxLayout(inner)
        self.content.setContentsMargins(32, 28, 32, 32)
        self.content.setSpacing(18)

    def row(self, spacing=24):
        layout = QHBoxLayout()
        layout.setSpacing(spacing)
        self.content.addLayout(layout)
        return layout

    def gap(self, px=14):
        self.content.addSpacing(px)

    def read_only_note(self, what, command):
        """ One quiet line explaining how to change this until the app can. """
        w = label(f"{what} from here comes in the next update. Until then, run "
                  f"<b style='color:#F2F2F0'>{command}</b> in a terminal.", "Note", wrap=True)
        self.content.addWidget(w)
        return w

    def finish(self):
        self.content.addStretch(1)

    def update_snapshot(self, snapshot):
        """ Called with every poller snapshot (see poller.StatsPoller). """
