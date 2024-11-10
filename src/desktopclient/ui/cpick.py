from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSlider
from PySide6.QtGui import QPainter, QBrush, QColor, QLinearGradient


class GradientSlider(QSlider):
    def __init__(self, orientation=Qt.Orientation.Vertical, parent=None):
        super().__init__(orientation, parent)
        self.setMinimum(0)
        self.setMaximum(360)  # Max to match the full range of the HSV hue
        self.setValue(300)  # Example starting position for the handle
        self.setTickPosition(QSlider.TickPosition.NoTicks)
        self.setOrientation(orientation)

        # Extend the handle to go outside the gradient area
        self.setStyleSheet("""
            QSlider::groove:horizontal {
                background: transparent;
                height: 0px;
            }

            QSlider::groove:vertical {
                background: transparent;
                width: 0px;
            }
                    
            QSlider:horizontal {
                min-height: 28px;
                max-height: 28px;
            }          
            
            QSlider:vertical {
                min-width: 28px;
                max-width: 28px;
            }

            QSlider::handle:horizontal {
                width: 22px;
                height: 80px;
                margin: -24px -12px;
                background: white;
                border: 2px solid black;
            }

            QSlider::handle:vertical {
                height: 22px;
                width: 80px;
                margin: -12px -24px;
                background: white;
                border: 2px solid black;
            }
                          
        """)

    def paintEvent(self, ev):
        painter = QPainter(self)
        rect = self.rect()

        if self.orientation() == Qt.Orientation.Horizontal:
            rect.adjust(14, 6, -14, -6)
            gradient = QLinearGradient(rect.left(), 0, rect.right(), 0)
        else:
            rect.adjust(6, 14, -6, -14)
            gradient = QLinearGradient(0, rect.top(), 0, rect.bottom())

        for i in range(360):
            hue = i / 360
            color = QColor.fromHsvF(hue, 1.0, 1.0)
            gradient.setColorAt(hue, color)
        painter.fillRect(rect, QBrush(gradient))

        super().paintEvent(ev)
