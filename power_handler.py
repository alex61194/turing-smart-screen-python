import os
import sys
import time
import signal
import threading

SHUTDOWN_SIGNAL = ".shutdown_signal"


def signal_shutdown():
    open(SHUTDOWN_SIGNAL, "a").close()


def clear_shutdown():
    if os.path.exists(SHUTDOWN_SIGNAL):
        os.remove(SHUTDOWN_SIGNAL)


def wait_for_signal():
    while not os.path.exists(SHUTDOWN_SIGNAL):
        time.sleep(1)


class PowerHandler:
    def __init__(self):
        self._on_suspend = None
        self._on_resume = None
        self._running = False
        self._thread = None

    def set_callbacks(self, on_suspend=None, on_resume=None):
        self._on_suspend = on_suspend
        self._on_resume = on_resume

    def _monitor(self):
        while self._running:
            if os.path.exists(SHUTDOWN_SIGNAL):
                if self._on_suspend:
                    self._on_suspend()
                os.remove(SHUTDOWN_SIGNAL)
                wait_for_signal()
                if self._on_resume:
                    self._on_resume()

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._monitor, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
