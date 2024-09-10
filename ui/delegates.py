"""
Useful delegates for Qt
"""

from qtpy.QtWidgets import QStyledItemDelegate, QStyle


class NoFocusDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        option.state = QStyle.StateFlag.State_Enabled
        super(NoFocusDelegate, self).paint(painter, option, index)