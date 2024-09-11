from PySide6.QtWidgets import QFrame, QLabel, QHBoxLayout
from PySide6.QtGui import QMouseEvent
from PySide6.QtCore import Qt
from enum import Enum

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
