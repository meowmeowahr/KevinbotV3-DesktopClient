import serial
import serial.tools.list_ports
import serial.tools.list_ports_linux
from loguru import logger
from PySide6.QtCore import QObject, Signal
from xbee import XBee


class XBeeManager(QObject):
    # Define signals
    on_data = Signal(dict)
    on_error = Signal(str)
    on_reject = Signal()
    on_open = Signal()
    on_close = Signal()

    def __init__(self, port=None, baud=9600, flow_control=False, api_escaped=False):
        super().__init__()
        self.port = port
        self.baud = baud
        self.flow_control = flow_control
        self.api_escaped = api_escaped
        self.serial = None
        self.xbee = None

    def get_available_ports(self, system=True) -> list[str]:
        """Return a list of available serial ports."""
        port_strs = []
        for port in serial.tools.list_ports.comports():
            if not system and not port.device.startswith("/dev/ttyS") or system:
                port_strs.append(port.device)
        return port_strs

    def open(self):
        """Open the serial port and initialize the XBee connection."""
        try:
            # Open the serial connection
            self.serial = serial.Serial(
                port=self.port, baudrate=self.baud, rtscts=self.flow_control, timeout=1
            )

            # Initialize XBee with API mode (escaped/unescaped)
            self.xbee = XBee(
                self.serial, escaped=self.api_escaped, callback=self._handle_packet
            )

            # Emit the on_open signal
            self.on_open.emit()

        except serial.SerialException as e:
            self.on_error.emit(f"Serial error: {e!s}")

    def halt(self):
        if self.xbee:
            self.xbee.halt()
        else:
            logger.warning("Could not halt non-existent XBee connection")

    def is_open(self) -> bool:
        """Check if the serial port is open."""
        return self.serial is not None and self.serial.is_open

    def close(self):
        """Close the XBee and serial connection."""
        if self.xbee:
            self.xbee.halt()  # Stop the XBee processing
            self.xbee = None
        if self.serial and self.serial.is_open:
            self.serial.close()
            self.serial = None
        # Emit the on_close signal
        self.on_close.emit()

    def set_port(self, port):
        """Set the serial port."""
        self.port = port

    def set_baud(self, baud):
        """Set the baud rate."""
        self.baud = baud

    def set_flow_control(self, flow_control):
        """Set the flow control (RTS/CTS)."""
        self.flow_control = flow_control

    def set_api_escaped(self, escaped):
        """Set API mode (escaped/unescaped)."""
        self.api_escaped = escaped

    def _handle_packet(self, packet):
        """Handle incoming packets from the XBee."""
        try:
            # Emit the full packet through on_data
            self.on_data.emit(packet)
        except Exception as e:
            self.on_error.emit(f"Error handling packet: {e!r}")

    def broadcast(self, message: str):
        """Send a broadcast message to all devices."""
        try:
            if self.xbee:
                self.xbee.send(
                    "tx",
                    dest_addr=b"\x00\x00",
                    data=bytes(f"{message}\n", "utf-8"),
                )
                logger.trace(f"Broadcasted message: {message}")
            else:
                self.on_reject.emit()
                logger.warning(
                    f"Cannot broadcast message, {message}: XBee not connected"
                )
        except Exception as e:
            self.on_error.emit(f"Error broadcasting message: {e!r}")
