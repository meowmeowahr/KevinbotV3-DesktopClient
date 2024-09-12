"""
Unit tests for widgets
"""


from PySide6.QtCore import Qt

from ui.widgets import WarningBar, Severity

def test_warning_bar_basic(qtbot):
    bar = WarningBar("test", closeable=False)
    bar.setVisible(True)
    qtbot.addWidget(bar)
    assert bar._text.text() == "test"
    qtbot.mouseClick(bar, Qt.MouseButton.LeftButton)
    assert bar.isVisible() is True

def test_warning_bar_close(qtbot):
    bar = WarningBar("test", closeable=True)
    bar.setVisible(True)
    qtbot.addWidget(bar)
    qtbot.mouseClick(bar, Qt.MouseButton.LeftButton)
    assert bar.isVisible() is False

def test_warning_bar_severe(qtbot):
    bar = WarningBar("test", severity=Severity.WARN)
    assert bar.styleSheet() == "background-color: #ffc107;"
    bar = WarningBar("test", severity=Severity.SEVERE)
    assert bar.styleSheet() == "background-color: #ef5350;"
    