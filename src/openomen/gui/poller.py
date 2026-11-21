"""
Background polling of hardware state.

All core reads (sysfs, /proc, nvidia-smi) run on a worker thread so the
window never stalls; results arrive on the GUI thread through Qt signals.
"""

import logging
import time
import traceback

from PySide6.QtCore import QObject, QRunnable, QThread, QThreadPool, QTimer, Signal, Slot

from ..core import cpu, fans, gpu, power, rgb

POLL_INTERVAL_MS = 1500

log = logging.getLogger("openomen")


class _StatsWorker(QObject):
    updated = Signal(dict)

    def __init__(self):
        super().__init__()
        self._sampler = None
        self._timer = None

    @Slot()
    def start(self):
        # Created here so the timer lives on the worker thread.
        self._sampler = cpu.CpuSampler()
        try:
            self._sampler.sample()  # prime, so the first tick has real usage
        except OSError:
            pass
        self._timer = QTimer()
        self._timer.setInterval(POLL_INTERVAL_MS)
        self._timer.timeout.connect(self.poll)
        self._timer.start()
        QTimer.singleShot(300, self.poll)

    @Slot()
    def poll(self):
        snapshot = {"time": time.time()}
        for key, read in (
            ("fan", fans.get_fan_status),
            ("power", power.get_power_status),
            ("cpu", lambda: cpu.get_cpu_stats(self._sampler)),
            ("gpus", lambda: [gpu.public(g) for g in gpu.query_gpus()]),
            ("rgb", rgb.get_rgb_status),
        ):
            try:
                snapshot[key] = read()
            except Exception:  # one broken sensor must not stop the dashboard
                log.error(f"Error while reading {key}:\n{traceback.format_exc()}")
                snapshot[key] = None
        self.updated.emit(snapshot)

    @Slot()
    def stop(self):
        if self._timer:
            self._timer.stop()


class StatsPoller(QObject):
    """ Emits `updated(snapshot)` every POLL_INTERVAL_MS with fan/power/cpu/gpu/rgb state. """

    updated = Signal(dict)
    _stop_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = QThread()
        self._thread.setObjectName("openomen-poller")
        self._worker = _StatsWorker()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.start)
        self._worker.updated.connect(self.updated)
        self._stop_requested.connect(self._worker.stop)

    def start(self):
        self._thread.start()

    def stop(self):
        """ Stop polling and wait for the worker thread. Safe to call more than once. """
        if not self._thread.isRunning():
            return
        self._stop_requested.emit()
        self._thread.quit()
        self._thread.wait(5000)


class _Task(QRunnable):
    class _Signals(QObject):
        done = Signal(object, object)  # result, error

    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        self.signals = self._Signals()

    def run(self):
        try:
            self.signals.done.emit(self.fn(), None)
        except Exception as e:  # handed to the callback
            self.signals.done.emit(None, e)


_running = set()


def run_in_background(fn, callback):
    """ Run fn() on the thread pool and call callback(result, error) on the GUI thread. """
    task = _Task(fn)
    _running.add(task)

    def finished(result, error):
        _running.discard(task)
        callback(result, error)

    task.signals.done.connect(finished)
    QThreadPool.globalInstance().start(task)
