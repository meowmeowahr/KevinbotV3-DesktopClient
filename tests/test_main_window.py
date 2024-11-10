"""
Unit tests for main window
"""

import queue

import pytest
from PySide6.QtWidgets import QApplication


def test_main_window(qtbot):
    import kevinbot_desktopclient.main as main

    app = QApplication.instance()
    if app:
        win = main.MainWindow(app, queue.Queue())
        assert win.isVisible()
        win.close()
    else:  # pragma: no cover
        pytest.fail("No running QApplication instance found")
