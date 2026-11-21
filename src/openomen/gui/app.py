""" Entry point for `openomen-gui`. """

import argparse
import logging
import signal
import sys

from .. import VERSION
from ..core.runtime import is_root, restore_child_library_path


def setup_logging(recent_handler):
    """
    Core reports unreadable sensors through the 'openomen' logger. The dashboard
    polls every 1.5 s, so print each distinct message to stderr only once and
    keep them for the System page.
    """
    printed = set()

    class OncePerMessage(logging.Filter):
        def filter(self, record):
            message = record.getMessage()
            if message in printed:
                return False
            printed.add(message)
            return True

    stderr = logging.StreamHandler(sys.stderr)
    stderr.setFormatter(logging.Formatter("openomen: %(message)s"))
    stderr.addFilter(OncePerMessage())
    logger = logging.getLogger("openomen")
    logger.handlers[:] = [stderr, recent_handler]
    logger.setLevel(logging.WARNING)
    logger.propagate = False


def main(argv=None):
    parser = argparse.ArgumentParser(prog="openomen-gui",
                                     description="OpenOMEN Control Center (read-only preview)")
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument("--page", choices=["overview", "fans", "power", "keyboard", "system"],
                        help="Page to open on start")
    args, qt_args = parser.parse_known_args(argv)

    restore_child_library_path()
    if is_root():
        print("openomen-gui: run the app as your normal user, not with sudo. "
              "It will ask for permission itself when it needs to change settings.", file=sys.stderr)

    # Imported here so `openomen-gui --version` works without a display.
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from . import theme
    from .pages.system import RecentLogHandler
    from .window import MainWindow

    recent = RecentLogHandler()
    setup_logging(recent)

    app = QApplication([sys.argv[0]] + qt_args)
    app.setApplicationName("OpenOMEN")
    app.setApplicationDisplayName("OpenOMEN")
    app.setDesktopFileName("openomen-gui")
    theme.apply(app)

    window = MainWindow(log_handler=recent)
    if args.page:
        window.show_page(args.page)
    window.show()

    # Stop the polling thread however the app ends (window closed, Ctrl+C, logout).
    app.aboutToQuit.connect(window.poller.stop)

    # Let Ctrl+C in the terminal close the app. Python only runs signal handlers
    # when it gets control, so wake it up regularly while Qt's loop runs.
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    wake = QTimer()
    wake.timeout.connect(lambda: None)
    wake.start(250)
    return app.exec()
