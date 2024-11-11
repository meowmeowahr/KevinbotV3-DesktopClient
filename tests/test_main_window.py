"""
Unit tests for main window
"""

import queue

import pytest
from PySide6.QtWidgets import QApplication


@pytest.mark.usefixtures("qtbot")
def test_main_window():
    from kevinbot_desktopclient import main

    app = QApplication.instance()
    if app:
        win = main.MainWindow(app, queue.Queue())
        assert win.isVisible()
        win.close()
    else:  # pragma: no cover
        pytest.fail("No running QApplication instance found")
