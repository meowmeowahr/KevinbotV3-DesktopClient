"""
Unit tests for delegates
"""

from PySide6.QtWidgets import QTreeView, QStyleOptionViewItem, QStyle
from PySide6.QtCore import QModelIndex
from PySide6.QtGui import QPainter
import pytest

from ui.delegates import NoFocusDelegate


# TODO: Clean up this (maybe) poor ChatGPT code
@pytest.fixture
def delegate_and_view(qtbot):
    # Create a QTreeView as the view to use with the delegate
    view = QTreeView()
    delegate = NoFocusDelegate()

    # Assign the delegate to the view
    view.setItemDelegate(delegate)

    # Use qtbot to manage widgets
    qtbot.addWidget(view)
    return delegate, view


def test_no_focus_delegate_paint(delegate_and_view):
    delegate, view = delegate_and_view

    # Create a QPainter mock (or real instance if needed)
    painter = QPainter()

    # Create a QStyleOptionViewItem and QModelIndex mock (or real instance if needed)
    option = QStyleOptionViewItem()
    option.state = QStyle.StateFlag.State_HasFocus  # Initial state # type: ignore

    index = QModelIndex()  # Mock index or provide a valid one

    # Call the paint method
    delegate.paint(painter, option, index)

    # Assert that option.state is now set to State_Enabled
    assert option.state == QStyle.StateFlag.State_Enabled  # type: ignore
