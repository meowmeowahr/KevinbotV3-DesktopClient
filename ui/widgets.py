from PySide6.QtWidgets import QFrame, QLabel, QHBoxLayout, QVBoxLayout, QToolButton, QStackedWidget, QWidget
from PySide6.QtGui import QMouseEvent
from PySide6.QtCore import Qt, QSize, Signal
from enum import Enum
from functools import partial

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
        button.clicked.connect(partial(self.tab_stack.setCurrentIndex, self.tab_stack.count() - 1))
        button.clicked.connect(lambda: self.on_tab_changed.emit(self.tab_stack.count() - 1))


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
