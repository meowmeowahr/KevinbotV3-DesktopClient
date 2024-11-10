import hashlib
from enum import Enum
from functools import partial

import qtawesome as qta
from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont, QMouseEvent, QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from ui.util import initials as str2initials
from ui.util import rgb_to_hex as _rgb2hex


class Severity(Enum):
    WARN = 0
    SEVERE = 1


class WarningBar(QFrame):
    def __init__(self, text="", closeable=False, severity=Severity.WARN) -> None:
        super(WarningBar, self).__init__()

        self.closeable: bool = closeable

        self.setFrameShape(QFrame.Shape.Box)
        if severity == Severity.SEVERE:
            self.setStyleSheet("background-color: #ef5350;")
        elif severity == Severity.WARN:
            self.setStyleSheet("background-color: #ffc107;")
        self.setMinimumHeight(48)

        self._layout = QHBoxLayout()
        self.setLayout(self._layout)

        self._text = QLabel(text)
        # self.__text.setStyleSheet("font-weight: bold;")
        self._text.setObjectName("warning_bar_text")
        self._text.setProperty(
            "severity", "warn" if severity == Severity.WARN else "severe"
        )
        self._text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(self._text)

        self.setFixedHeight(self.minimumSizeHint().height())

    def mousePressEvent(self, event: QMouseEvent):
        if self.closeable:
            self.setVisible(False)
        event.accept()


class CustomTabWidget(QWidget):
    """
    A custom replacement for QTabWidget that uses a stacked widget to display tabs, and QToolButtons for switching between them.
    Only supports tabs on the North side for now
    """

    on_tab_changed = Signal(int)

    def __init__(self, parent=None):
        super(CustomTabWidget, self).__init__(parent)

        self._icon_size = QSize(36, 36)

        self.tab_stack = QStackedWidget(self)
        self.tab_buttons_layout = QHBoxLayout()
        self.tab_buttons_layout.setContentsMargins(0, 0, 0, 0)

        self.tab_buttons = []

        self.root_layout = QVBoxLayout()
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.addLayout(self.tab_buttons_layout)
        self.root_layout.addWidget(self.tab_stack)
        self.setLayout(self.root_layout)

    def addTab(self, widget, title, icon=None):
        self.tab_stack.addWidget(widget)
        button = QToolButton()
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        button.setCheckable(True)
        button.setAutoExclusive(True)
        button.setIconSize(self._icon_size)
        button.clicked.connect(
            partial(self.tab_stack.setCurrentIndex, self.tab_stack.count() - 1)
        )
        button.clicked.connect(
            lambda: self.on_tab_changed.emit(self.tab_stack.count() - 1)
        )

        if icon is not None:
            button.setIcon(icon)

        button.setText(title)
        self.tab_buttons.append(button)
        self.tab_buttons_layout.addWidget(button)

        if self.tab_stack.currentIndex() == len(self.tab_buttons) - 1:
            button.setChecked(True)

    @property
    def icon_size(self) -> QSize:
        return self._icon_size

    @icon_size.setter
    def icon_size(self, size: QSize) -> None:
        self._icon_size = size
        for button in self.tab_buttons:
            button.setIconSize(size)

    @property
    def current_index(self) -> int:
        return self.tab_stack.currentIndex()


class Profile(QLabel):
    def __init__(self, initials, parent=None):
        super().__init__(parent)
        self.initials = initials
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(64, 64)
        self.setText(self.initials)
        self.setStyleSheet(self.generate_stylesheet())

    def generate_stylesheet(self):
        # Create a hash from the initials
        hash_object = hashlib.md5(self.initials.encode())
        hex_digest = hash_object.hexdigest()

        # Use the first 6 characters of the hash as color components
        r1 = int(hex_digest[0:2], 16)
        g1 = int(hex_digest[2:4], 16)
        b1 = int(hex_digest[4:6], 16)

        r2 = int(hex_digest[6:8], 16)
        g2 = int(hex_digest[8:10], 16)
        b2 = int(hex_digest[10:12], 16)

        # Create gradient color stops
        color1 = f"rgb({r1}, {g1}, {b1})"
        color2 = f"rgb({r2}, {g2}, {b2})"

        # Define the stylesheet with a circular gradient
        stylesheet = f"""
        QLabel {{
            background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                                         stop: 0 {color1}, stop: 1 {color2});
            color: white;
            border-radius: {self.width() // 2}px;
            font-size: 22px;
            font-weight: bold;
            text-align: center;
        }}
        """
        return stylesheet

    def resizeEvent(self, event: QResizeEvent) -> None:
        self.setStyleSheet(self.generate_stylesheet())
        return super().resizeEvent(event)


class AuthorWidget(QFrame):
    """
    Widget meant to show an application author's information
    """

    def __init__(self) -> None:
        super().__init__()

        self._author_name = ""
        self._author_title = ""
        self._author_email = ""
        self._author_website = ""

        self.setFrameShape(QFrame.Shape.Box)

        self._layout = QHBoxLayout()
        self.setLayout(self._layout)

        self._profile = Profile(str2initials(self._author_name))
        self._layout.addWidget(self._profile)

        self._name_layout = QVBoxLayout()
        self._layout.addLayout(self._name_layout)

        self._author_name_label = QLabel(self._author_name)
        self._author_name_label.setFont(QFont(self.fontInfo().family(), 14))
        self._name_layout.addWidget(self._author_name_label)

        self._author_title_label = QLabel(self._author_title)
        self._name_layout.addWidget(self._author_title_label)

        self._layout.addStretch()

        self.author_site_button = QToolButton()
        self.author_site_button.setIcon(qta.icon("mdi6.web"))
        self.author_site_button.setIconSize(QSize(32, 32))
        self.author_site_button.clicked.connect(
            self.open_website, type=Qt.ConnectionType.UniqueConnection
        )
        self._layout.addWidget(self.author_site_button)

        self._author_email_button = QToolButton()
        self._author_email_button.setIcon(qta.icon("mdi6.email"))
        self._author_email_button.setIconSize(QSize(32, 32))
        self._author_email_button.clicked.connect(
            self.open_email, type=Qt.ConnectionType.UniqueConnection
        )
        self._layout.addWidget(self._author_email_button)

        self.setMaximumHeight(self.minimumSizeHint().height())

    @property
    def author_name(self) -> str:
        return self._author_name

    @author_name.setter
    def author_name(self, name: str) -> None:
        self._author_name = name
        self._author_name_label.setText(name)
        self._profile.setText(str2initials(name))
        self._profile.initials = str2initials(self._author_name)
        self._profile.setStyleSheet(self._profile.generate_stylesheet())

    @property
    def author_title(self) -> str:
        return self._author_title

    @author_title.setter
    def author_title(self, title: str) -> None:
        self._author_title = title
        self._author_title_label.setText(title)

    @property
    def author_email(self) -> str:
        return self._author_email

    @author_email.setter
    def author_email(self, email: str) -> None:
        self._author_email = email

    @property
    def author_website(self) -> str:
        return self._author_website

    @author_website.setter
    def author_website(self, website: str) -> None:
        self._author_website = website

    def open_website(self) -> None:  # pragma: no cover
        QDesktopServices.openUrl(QUrl(self._author_website))

    def open_email(self) -> None:  # pragma: no cover
        QDesktopServices.openUrl(QUrl(f"mailto:{self._author_email}"))


class ColorBlock(QFrame):
    """
    A simple widget ot show a single color
    """

    def __init__(self) -> None:
        super(ColorBlock, self).__init__()

        self.setFrameShape(QFrame.Shape.Box)
        self.setMinimumWidth(24)
        self.setMinimumHeight(10)

        self.setMaximumSize(128, 128)

    def set_color(self, color: str) -> None:
        """
        Sets the color of the widget
        """
        self.setStyleSheet(f"background-color: {color};")

    def set_rgb(self, rgb):
        """
        Sets the color of the widget in (r, g, b)
        """
        color_str = _rgb2hex(rgb)
        self.setStyleSheet(f"background-color: #{color_str};")
