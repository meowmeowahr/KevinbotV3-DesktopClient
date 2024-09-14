"""
Unit tests for main window
"""

import mock
import queue
from PySide6.QtWidgets import QApplication

def test_main_window(qtbot):
    import main

    win = main.MainWindow(QApplication.instance(), queue.Queue())
    assert win.isVisible()
    win.close()
