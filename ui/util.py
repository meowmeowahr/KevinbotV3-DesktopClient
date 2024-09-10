from collections.abc import Callable

from qtpy.QtGui import QIcon, QTransform
from qtpy.QtWidgets import QWidget, QTabWidget
from qtpy.QtCore import Qt

def rotate_icon(icon: QIcon, angle: float) -> QIcon:
    # Convert QIcon to QPixmap
    pixmap = icon.pixmap(64, 64)
    # Create a transformation for rotating
    transform = QTransform().rotate(angle)
    # Apply the transformation to the QPixmap
    rotated_pixmap = pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)
    # Convert back to QIcon
    return QIcon(rotated_pixmap)

def add_tabs(bar: QTabWidget, tabs: list[list[str | QIcon]]) -> list[QWidget | Callable]:

    widgets = []
    for tab_options in tabs:
        widget = QWidget()
        widgets.append(widget)
        bar.addTab(widget, rotate_icon(tab_options[1],
                                       90 if bar.tabPosition() in
                                             [QTabWidget.TabPosition.West, QTabWidget.TabPosition.East] else 0), "")

    return widgets