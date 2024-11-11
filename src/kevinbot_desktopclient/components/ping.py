import icmplib
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget


class PingWorker(QThread):
    ping_completed = Signal(object)
    on_error = Signal(Exception)

    def __init__(self, target: str, count: int, interval: float, timeout: int):
        super().__init__()
        self.target = target
        self.count = count
        self.interval = interval
        self.timeout = timeout

        self.running = True

    def run(self):
        # Perform a burst ping
        if not self.running:
            return
        try:
            response = icmplib.ping(
                self.target,
                interval=self.interval,
                count=self.count,
                timeout=self.timeout,
                privileged=False,
            )
        except (
            UnicodeError,
            icmplib.exceptions.ICMPSocketError,
            icmplib.exceptions.NameLookupError,
            icmplib.exceptions.SocketPermissionError,
            icmplib.exceptions.SocketAddressError,
        ) as e:
            self.on_error.emit(e)
            return
        result = response
        # Emit the result to the main thread
        self.ping_completed.emit(result)

    def stop(self):
        self.running = False
        self.wait()


class PingWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.root_layout = QHBoxLayout()
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.root_layout)

        # Label for displaying connection status and values
        self.label = QLabel("Not Connected")
        self.root_layout.addWidget(self.label)

        # Adjust initial style
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("font-size: 14px;")

    def set_values(self, values):
        # Calculate color for ping
        ping_color = self.get_color_based_on_value(values.avg_rtt, thresholds=(50, 150))
        jitter_color = self.get_color_based_on_value(values.jitter, thresholds=(20, 100))

        # Set colored text for ping and jitter
        self.label.setText(
            f"Ping: <span style='color:{ping_color}'>{values.avg_rtt:.0f} ms</span>, "
            f"Jitter: <span style='color:{jitter_color}'>{values.jitter:.0f} ms</span>"
        )

    def set_disconnected(self):
        self.label.setText("Not Connected")
        self.label.setStyleSheet("font-size: 14px;")

    def get_color_based_on_value(self, value, thresholds):
        """Return color hex based on value and thresholds for green, yellow, red."""
        low, high = thresholds
        if value <= low:
            return "#2ecc71"  # Green
        if value <= high:
            return "#f39c12"  # Yellow
        return "#e74c3c"  # Red
