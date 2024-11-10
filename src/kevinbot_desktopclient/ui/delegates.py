"""
Useful delegates for Qt
"""

from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem


class NoFocusDelegate(QStyledItemDelegate):
    def paint(self, painter, option: QStyleOptionViewItem, index):
        option.state = QStyle.StateFlag.State_Enabled  # type: ignore
        super(NoFocusDelegate, self).paint(painter, option, index)
