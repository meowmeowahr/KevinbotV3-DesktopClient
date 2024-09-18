"""
Unit tests for main window
"""

import pytest
import queue
from PySide6.QtWidgets import QApplication

def test_main_window(qtbot):
    import main

    app = QApplication.instance()
    if app:
        win = main.MainWindow(app, queue.Queue())
        assert win.isVisible()
        win.close()
    else: # pragma: no cover
        pytest.fail("No running QApplication instance found")