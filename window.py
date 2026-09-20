#!/usr/bin/env python3
"""
Comfy Studio - Native Qt6 WebEngine Isolated Desktop Window
Eliminates Google Chrome dependency. Completely self-contained in .venv.
"""
import sys
import os
import urllib.request
import json

from PyQt6.QtCore import QUrl, Qt, QTimer
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
from PyQt6.QtGui import QIcon

BACKEND_STATUS_URL = "http://127.0.0.1:5111/api/status"

class StudioWindow(QMainWindow):
    def __init__(self, url, title="Comfy Studio", icon_path=None):
        super().__init__()
        self.setWindowTitle(title)
        self.resize(1400, 920)
        self.setMinimumSize(960, 640)
        self._closing = False

        if icon_path and os.path.isfile(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Configure isolated web profile
        self.profile = QWebEngineProfile("comfy-studio-isolated", self)
        self.page = QWebEnginePage(self.profile, self)

        self.browser = QWebEngineView(self)
        self.browser.setPage(self.page)
        self.browser.setUrl(QUrl(url))
        self.setCentralWidget(self.browser)

        # In-page "Quit & Offload" only shuts down the backend server; it has
        # no way to close this native Qt window. Poll for the backend going
        # away (backend-initiated shutdown, or a crash) and close ourselves.
        # Require three consecutive failures: a single missed probe only means
        # the stdlib server was busy, and closing on that would tear the window
        # down mid-generation or during a slow start.
        self._consecutive_failures = 0
        self._backend_watchdog = QTimer(self)
        self._backend_watchdog.timeout.connect(self._check_backend_alive)
        self._backend_watchdog.start(1500)

    def _check_backend_alive(self):
        if self._closing:
            return
        try:
            with urllib.request.urlopen(BACKEND_STATUS_URL, timeout=1.5):
                self._consecutive_failures = 0
        except Exception:
            self._consecutive_failures += 1
            if self._consecutive_failures >= 3:
                self._closing = True
                self._backend_watchdog.stop()
                self.close()

    def closeEvent(self, event):
        """Clean shutdown hook when user closes the window."""
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:5111/api/shutdown",
                data=b"{}",
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=1.5):
                pass
        except Exception:
            pass
        event.accept()

def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5111"
    title = sys.argv[2] if len(sys.argv) > 2 else "Comfy Studio"
    icon = sys.argv[3] if len(sys.argv) > 3 else os.path.join(
        os.path.dirname(__file__), "static", "icon.svg")

    app = QApplication(sys.argv)
    app.setApplicationName(title)
    # Wayland takes the xdg-shell app_id from the desktop file name; without
    # this Qt falls back to the interpreter basename ("python") and the window
    # never matches comfy-studio.desktop, so the taskbar shows a generic icon.
    app.setDesktopFileName("comfy-studio")
    if os.path.isfile(icon):
        app.setWindowIcon(QIcon(icon))

    window = StudioWindow(url, title, icon)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
