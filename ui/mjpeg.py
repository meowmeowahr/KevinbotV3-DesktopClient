"""
PySide6 MJPEG Stream Viewer and Widget
"""


import requests
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget, QSizePolicy
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtCore import QThread, Signal, Qt
from io import BytesIO
from PIL import Image
import urllib3

from loguru import logger


class MJPEGStreamThread(QThread):
    frame_received = Signal(QImage)

    def __init__(self, stream_url):
        super().__init__()
        self.stream_url = stream_url
        self._running = True

    def run(self):
        try:
            with requests.get(self.stream_url, stream=True) as r:
                buffer = b''
                for chunk in r.iter_content(chunk_size=1024):
                    if not self._running:
                        break
                    buffer += chunk
                    # Find the start and end of a frame
                    start_idx = buffer.find(b'\xff\xd8')  # Start of JPEG
                    end_idx = buffer.find(b'\xff\xd9')    # End of JPEG
                    if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                        # Extract the frame and convert it to QImage
                        frame_data = buffer[start_idx:end_idx + 2]
                        buffer = buffer[end_idx + 2:]

                        # Convert to QImage
                        img = Image.open(BytesIO(frame_data))
                        img = img.convert('RGB')
                        qimg = QImage(img.tobytes(), img.width, img.height, QImage.Format.Format_RGB888)
                        self.frame_received.emit(qimg)
        except (urllib3.exceptions.MaxRetryError, urllib3.exceptions.ConnectionError, requests.exceptions.ConnectionError, ConnectionRefusedError) as e:
            logger.error(f"Could not open MJPEG stream, {repr(e)}")

    def stop(self):
        self._running = False


class MJPEGViewer(QWidget):
    def __init__(self, stream_url):
        super().__init__()
        # QLabel for displaying the image
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)

        # Set layout
        layout = QVBoxLayout()
        layout.addWidget(self.label)
        self.setLayout(layout)

        # Start the MJPEG stream
        self.mjpeg_thread = MJPEGStreamThread(stream_url)
        self.mjpeg_thread.frame_received.connect(self.update_image)
        self.mjpeg_thread.start()

        super().setMinimumWidth(200)

        # Store the current pixmap
        self.current_pixmap = None

    def update_image(self, qimg):
        pixmap = QPixmap.fromImage(qimg)
        aspect = pixmap.width() / pixmap.height()
        super().setMinimumHeight(round(200 / aspect))
        self.current_pixmap = pixmap
        self.apply_scaling()

    def apply_scaling(self):
        if self.current_pixmap:
            # Scale the pixmap to fit the label's current size
            scaled_pixmap = self.current_pixmap.scaled(self.label.size(),
                                                       Qt.AspectRatioMode.KeepAspectRatio,
                                                       Qt.TransformationMode.SmoothTransformation)
            self.label.setPixmap(scaled_pixmap)

    def resizeEvent(self, event):
        # Reapply scaling when the window is resized
        self.apply_scaling()

    def closeEvent(self, event):
        self.mjpeg_thread.stop()
        self.mjpeg_thread.wait()
        event.accept()
