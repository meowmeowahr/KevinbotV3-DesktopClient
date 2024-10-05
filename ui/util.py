from typing import Tuple

from urllib.parse import urlparse, urlunparse

from PySide6.QtGui import QIcon, QTransform
from PySide6.QtWidgets import QWidget, QTabWidget
from PySide6.QtCore import Qt


def rotate_icon(icon: QIcon, angle: float) -> QIcon:
    # Convert QIcon to QPixmap
    pixmap = icon.pixmap(64, 64)
    # Create a transformation for rotating
    transform = QTransform().rotate(angle)
    # Apply the transformation to the QPixmap
    rotated_pixmap = pixmap.transformed(
        transform, Qt.TransformationMode.SmoothTransformation
    )
    # Convert back to QIcon
    return QIcon(rotated_pixmap)


def add_tabs(bar: QTabWidget, tabs: list[Tuple[str, QIcon]]) -> list[QWidget]:

    widgets = []
    for tab_options in tabs:
        widget = QWidget()
        widgets.append(widget)
        bar.addTab(
            widget,
            rotate_icon(
                tab_options[1],
                (
                    90
                    if bar.tabPosition()
                    in [QTabWidget.TabPosition.West, QTabWidget.TabPosition.East]
                    else 0
                ),
            ),
            "",
        )

    return widgets


def initials(phrase):
    words = phrase.split()
    result = ""
    for i in range(len(words)):
        result += words[i][0].upper()
    return result


def rgb_to_hex(rgb):
    return "%02x%02x%02x" % tuple(rgb)


def change_url_port(url, new_port):
    # Parse the URL into components
    parsed_url = urlparse(url)

    # Replace the port (or add it if not present)
    netloc = parsed_url.hostname
    if new_port:
        netloc += f":{new_port}"

    # Rebuild the URL with the new port
    updated_url = urlunparse(parsed_url._replace(netloc=netloc))
    return updated_url