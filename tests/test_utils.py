"""
Unit tests for UI utils
"""

import pytest
from kevinbot_desktopclient.ui.util import add_tabs, change_url_port, initials, rgb_to_hex, rotate_icon
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QTabWidget


@pytest.mark.usefixtures("qtbot")
def test_tab_generator():
    tabs = [
        ("Test1", QIcon()),
        ("Test2", QIcon()),
    ]
    tabbar = QTabWidget()

    add_tabs(tabbar, tabs)

    assert tabbar.count() == 2


@pytest.mark.usefixtures("qtbot")
def test_icon_rotate():
    icon = QIcon()

    assert rotate_icon(icon, 90).isNull()
    assert rotate_icon(icon, -90).isNull()


def test_initials():
    assert initials("John Doe") == "JD"
    assert initials("john doe") == "JD"


def test_rgb2hex():
    assert rgb_to_hex((255, 127, 0)).upper() == "FF7F00"


def test_url_port():
    assert change_url_port("http://localhost", 5000) == "http://localhost:5000"
    assert change_url_port("https://example.com:433", 80) == "https://example.com:80"
