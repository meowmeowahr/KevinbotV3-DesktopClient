"""
Unit tests for main window
"""

import mock
import queue
from PySide6.QtWidgets import QApplication

def test_main_window(qtbot):
    import main

    with mock.patch.object(QApplication, "exit"):
        main.app = QApplication.instance() # type: ignore
        if main.app:
            win = main.MainWindow(main.app, queue.Queue())
            assert win.isVisible()
            win.close()
