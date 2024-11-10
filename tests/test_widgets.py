"""
Unit tests for widgets
"""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QWidget
from kevinbot_desktopclient.ui.widgets import (
    AuthorWidget,
    ColorBlock,
    CustomTabWidget,
    Profile,
    Severity,
    WarningBar,
)


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


def test_profile(qtbot):
    profile = Profile("JD")
    assert profile.initials == "JD"

    profile.resizeEvent(QResizeEvent(QSize(100, 100), QSize(64, 64)))


def test_author_widget(qtbot):
    author_widget = AuthorWidget()
    author_widget.author_name = "John Doe"
    author_widget.author_title = "Software Developer"
    author_widget.author_email = "johndoe@example.com"
    author_widget.author_website = "https://example.com"
    assert author_widget._author_name_label.text() == "John Doe"
    assert author_widget._author_title_label.text() == "Software Developer"
    assert author_widget.author_email == "johndoe@example.com"
    assert author_widget.author_website == "https://example.com"
    assert author_widget.author_name == "John Doe"
    assert author_widget.author_title == "Software Developer"


def test_color_block(qtbot):
    color_block = ColorBlock()
    color_block.set_rgb(
        (
            255,
            255,
            127,
        )
    )
    assert color_block.styleSheet() == "background-color: #ffff7f;"
    color_block.set_color("#f44336")
    assert color_block.styleSheet() == "background-color: #f44336;"
