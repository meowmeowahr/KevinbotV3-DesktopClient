"""
Unit tests for main window
"""

import main
import mock
from PySide6.QtWidgets import QApplication

def test_main_window(qtbot):
    with mock.patch.object(QApplication, "exit"):
        main.app = QApplication.instance() # type: ignore
        win = main.MainWindow()
        win.close()
