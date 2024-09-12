"""
Unit tests for UI utils
"""


from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QTabWidget

from ui.util import add_tabs, rotate_icon


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