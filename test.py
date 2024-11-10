import sys
from icmplib import ping
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget


class PingWorker(QThread):
    # Signal to send the ping result back to the main thread
    ping_completed = Signal(object)

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
        response = ping(self.target, interval=0.3)
        result = response.avg_rtt if response.is_alive else None
        # Emit the result to the main thread
        self.ping_completed.emit(result)

    def stop(self):
        self.running = False
        self.wait()


class PingApp(QWidget):
    def __init__(self, target, burst_count=4, interval=300, burst_delay=4000):
        super().__init__()
        self.target = target
        self.burst_count = burst_count
        self.interval = interval
        self.burst_delay = burst_delay
        self.current_burst = 0
        self.burst_results = []

        # Setup UI
        self.setWindowTitle("Ping Monitor")
        self.setGeometry(100, 100, 300, 200)
        self.label = QLabel("Pinging...", alignment=Qt.AlignCenter)
        layout = QVBoxLayout()
        layout.addWidget(self.label)
        self.setLayout(layout)

        # Timer for individual pings in a burst
        self.ping_timer = QTimer()
        self.ping_timer.setInterval(self.interval)
        self.ping_timer.timeout.connect(self.perform_ping)

        # Timer for the delay between bursts
        self.burst_timer = QTimer()
        self.burst_timer.setInterval(self.burst_delay)
        self.burst_timer.setSingleShot(True)
        self.burst_timer.timeout.connect(self.start_burst)

        # Initialize the ping worker
        self.ping_worker = PingWorker(self.target, 4, 0.3, 1)
        self.ping_worker.ping_completed.connect(self.handle_ping_result)

        # Start the first burst of pings
        self.start_burst()

    def start_burst(self):
        self.current_burst = 0
        self.burst_results = []
        self.ping_timer.start()  # Start sending pings at regular intervals

    def perform_ping(self):
        if not self.ping_worker.isRunning():
            self.ping_worker.start()

    def handle_ping_result(self, result):
        # Collect the result and update burst state
        self.burst_results.append(result)
        self.current_burst += 1

        if self.current_burst >= self.burst_count:
            # End the burst when we reach the count
            self.ping_timer.stop()
            self.update_ping_result()
            self.burst_timer.start()  # Start delay timer for the next burst

    def update_ping_result(self):
        if all(result is None for result in self.burst_results):
            text = "Ping failed"
        else:
            text = "Ping times: " + ", ".join(f"{r:.1f} ms" if r is not None else "N/A" for r in self.burst_results)
        self.label.setText(text)

    def closeEvent(self, event):
        # Stop any ongoing timers and worker to exit cleanly
        self.ping_timer.stop()
        self.burst_timer.stop()
        self.ping_worker.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PingApp("kevinbotv3.lan")
    window.show()
    sys.exit(app.exec())
