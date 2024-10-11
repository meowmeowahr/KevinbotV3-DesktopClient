"""
PySide6 MJPEG Stream Viewer and Widget
"""


import requests
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget, QSizePolicy
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtCore import QThread, Signal, Qt
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import textwrap
import urllib3

from loguru import logger


def create_image_with_text(text1, text2, image_size=(400, 400), font_path=None, wrap_width=60):
    # Create a blank image with white background
    image = Image.new("RGB", image_size, "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(16)

    # Word wrap the text
    wrapped_text1 = textwrap.fill(text1, width=wrap_width)
    wrapped_text2 = textwrap.fill(text2, width=wrap_width)

    # Combine the texts with some space between them
    combined_text = f"{wrapped_text1}\n\n{wrapped_text2}"

    # Calculate text size
    _, _, text_width, text_height = draw.textbbox((0, 0), combined_text, font=font)

    # Calculate position to center the text
    position = ((image_size[0] - text_width) // 2, (image_size[1] - text_height) // 2)

    # Draw the text on the image
    draw.text(position, combined_text, font=font, fill="black")

    return image


class MJPEGStreamThread(QThread):
    frame_received = Signal(QImage)

    def __init__(self, stream_url):
        super().__init__()
        self.stream_url = stream_url

    def run(self):
        try:
            with requests.get(self.stream_url, stream=True, timeout=10) as r:
                buffer = b''
                for chunk in r.iter_content(chunk_size=1024):
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
        except (urllib3.exceptions.MaxRetryError, urllib3.exceptions.ConnectionError, requests.exceptions.ConnectionError, ConnectionRefusedError, urllib3.exceptions.ProtocolError, requests.exceptions.ChunkedEncodingError, requests.exceptions.ReadTimeout) as e:
            logger.error(f"Could not open MJPEG stream, {repr(e)}")

            # Create a fake frame that displays description of error
            img = create_image_with_text("Error", repr(e), (640, 480,))
            img = img.convert('RGB')
            qimg = QImage(img.tobytes(), img.width, img.height, QImage.Format.Format_RGB888)
            self.frame_received.emit(qimg)


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
        self.mjpeg_thread.terminate()
        event.accept()
