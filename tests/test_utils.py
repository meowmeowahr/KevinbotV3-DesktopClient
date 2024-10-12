"""
Unit tests for UI utils
"""

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QTabWidget

from ui.util import add_tabs, rotate_icon, initials, rgb_to_hex, change_url_port


def test_tab_generator(qtbot):
    tabs = [
        ("Test1", QIcon()),
        ("Test2", QIcon()),
    ]
    tabbar = QTabWidget()

    add_tabs(tabbar, tabs)

    assert tabbar.count() == 2


def test_icon_rotate(qtbot):
    icon = QIcon()

    assert rotate_icon(icon, 90).isNull() and rotate_icon(icon, -90).isNull()


def test_initials():
    assert initials("John Doe") == "JD"
    assert initials("john doe") == "JD"


def test_rgb2hex():
    assert rgb_to_hex((255, 127, 0)).upper() == "FF7F00"

def test_url_port():
    assert change_url_port("http://localhost", 5000) == "http://localhost:5000"
    assert change_url_port("https://example.com:433", 80) == "https://example.com:80"