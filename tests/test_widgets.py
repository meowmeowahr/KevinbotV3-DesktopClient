"""
Unit tests for widgets
"""


from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QSize

from ui.widgets import WarningBar, Severity, CustomTabWidget

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

def test_warning_bar_severity(qtbot):
    bar = WarningBar("test", severity=Severity.WARN)
    assert bar.styleSheet() == "background-color: #ffc107;"
    bar = WarningBar("test", severity=Severity.SEVERE)
    assert bar.styleSheet() == "background-color: #ef5350;"
    

def test_custom_tab_widget(qtbot):
    tab_widget = CustomTabWidget()
    assert tab_widget.tab_stack.count() == 0
    tab_widget.addTab(QWidget(), "Tab 1")
    assert tab_widget.current_index == 0
    assert tab_widget.tab_stack.count() == 1
    tab_widget.icon_size = QSize(48, 48)
    assert tab_widget.icon_size == QSize(48, 48)
    assert tab_widget.tab_buttons[0].iconSize() == QSize(48, 48)