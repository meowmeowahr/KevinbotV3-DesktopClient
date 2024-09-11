import queue
import sys
import platform
import threading
from typing import Tuple

import qdarktheme as qtd
import qtawesome as qta
from loguru import logger
from PySide6.QtCore import QSize, QSettings, qVersion, Qt, QTimer
from PySide6.QtGui import QIcon, QCloseEvent
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QMainWindow, QWidget, QApplication, QTabWidget, QToolBox, QLabel, \
    QRadioButton, QSplitter, QTextEdit, QPushButton, QFileDialog, QGridLayout, QComboBox, QCheckBox

import ansi2html

from ui.util import add_tabs
from ui.widgets import WarningBar
from components import controllers, ControllerManagerWidget, begin_controller_backend
from components.xbee import XBeeManager

import constants

__version__ = "0.0.0"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Kevinbot Desktop Client {__version__}")

        # Settings Manager
        self.settings = QSettings("meowmeowahr", "KevinbotDesktopClient", self)

        # Remembered position
        if self.settings.contains("window/x"):
            # noinspection PyTypeChecker
            self.setGeometry(self.settings.value("window/x", type=int), # type: ignore
                             self.settings.value("window/y", type=int), # type: ignore
                             self.settings.value("window/width", type=int), # type: ignore
                             self.settings.value("window/height", type=int)) # type: ignore

        # Theme
        theme = self.settings.value("window/theme", "dark")
        if theme == "dark":
            qtd.setup_theme("dark", additional_qss="#warning_bar_text{color: #050505;}")
            qta.dark(app)
        elif theme == "light":
            qtd.setup_theme("light")
            qta.light(app)
        else:
            qtd.setup_theme("auto")

        # Timers
        self.logger_timer = QTimer()

        self.root_widget = QWidget()
        self.setCentralWidget(self.root_widget)

        self.root_layout = QVBoxLayout()
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_widget.setLayout(self.root_layout)

        # Controller
        self.controller_manager = ControllerManagerWidget(slots=1)

        # Communications
        self.xbee = XBeeManager(
            self.settings.value("comm/port", ""),
            self.settings.value("comm/baud", 921600, type=int), # type: ignore
            self.settings.value("comm/fc", False, type=bool), # type: ignore
            self.settings.value("comm/escaped", False, type=bool), # type: ignore
        )

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setIconSize(QSize(32, 32))
        self.tabs.setTabPosition(QTabWidget.TabPosition.West)
        self.root_layout.addWidget(self.tabs)

        tabs: list[Tuple[str, QIcon]] = [
            ("Main", qta.icon("mdi6.hub")),
            ("Connections", qta.icon("mdi6.transit-connection-variant")),
            ("Debug", qta.icon("mdi6.bug")),
            ("Settings", qta.icon("mdi6.cog")),
            ("About", qta.icon("mdi6.information-slab-circle")),
        ]
        self.main, self.connection_widget, self.debug, self.settings_widget, self.about_widget = add_tabs(self.tabs, tabs)

        self.settings_widget.setLayout(self.settings_layout(self.settings))
        self.debug.setLayout(self.debug_layout(self.settings))
        self.connection_widget.setLayout(self.connection_layout(self.settings))

        self.show()

    def settings_layout(self, settings: QSettings):
        layout = QVBoxLayout()

        toolbox = QToolBox()
        layout.addWidget(toolbox)

        theme_widget = QWidget()
        toolbox.addItem(theme_widget, "Theme and Appearance")

        theme_layout = QVBoxLayout()
        theme_widget.setLayout(theme_layout)

        theme_warning = WarningBar("Restart required to apply theme")
        theme_layout.addWidget(theme_warning)

        dark_mode_layout = QHBoxLayout()
        theme_layout.addLayout(dark_mode_layout)

        dark_mode_label = QLabel("Style")
        dark_mode_layout.addWidget(dark_mode_label)

        theme_dark = QRadioButton("Dark")
        dark_mode_layout.addWidget(theme_dark)

        theme_light = QRadioButton("Light")
        dark_mode_layout.addWidget(theme_light)

        theme_system = QRadioButton("System")
        dark_mode_layout.addWidget(theme_system)

        if settings.value("window/theme", "dark") == "dark":
            theme_dark.setChecked(True)
        elif settings.value("window/theme", "dark") == "light":
            theme_light.setChecked(True)
        else:
            theme_system.setChecked(True)

        theme_dark.clicked.connect(lambda: self.set_theme("dark"))
        theme_light.clicked.connect(lambda: self.set_theme("light"))
        theme_system.clicked.connect(lambda: self.set_theme("system"))

        return layout

    def debug_layout(self, _: QSettings):
        layout = QHBoxLayout()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        logger_widget = QWidget()
        splitter.addWidget(logger_widget)

        logger_layout = QVBoxLayout()
        logger_widget.setLayout(logger_layout)

        logger_top_bar = QHBoxLayout()
        logger_layout.addLayout(logger_top_bar)

        logger_clear = QPushButton("Clear")
        logger_clear.setIcon(qta.icon("mdi6.notification-clear-all"))
        logger_top_bar.addWidget(logger_clear)

        logger_export = QPushButton("Export")
        logger_export.setIcon(qta.icon("mdi6.export"))
        logger_top_bar.addWidget(logger_export)

        logger_area = QTextEdit()
        logger_area.setReadOnly(True)
        logger_area.setStyleSheet("background-color: black;")
        logger_clear.clicked.connect(logger_area.clear)
        logger_export.clicked.connect(lambda: self.export_logs(logger_area))
        logger_layout.addWidget(logger_area)

        self.logger_timer.setInterval(250)
        self.logger_timer.timeout.connect(lambda: self.update_logs(logger_area))
        self.logger_timer.start()

        return layout

    def connection_layout(self, settings: QSettings):
        layout = QHBoxLayout()

        splitter = QSplitter()
        layout.addWidget(splitter)

        # Controller
        controller_widget = QWidget()
        splitter.addWidget(controller_widget)

        controller_layout = QVBoxLayout()
        controller_widget.setLayout(controller_layout)

        controller_help = WarningBar("The first controller in the list will be the active controller.\n"
                                     "Drag-and-Drop controllers to select the active one")
        controller_layout.addWidget(controller_help)

        controller_layout.addWidget(self.controller_manager)

        # Comm
        comm_widget = QWidget()
        splitter.addWidget(comm_widget)

        comm_layout = QVBoxLayout()
        comm_widget.setLayout(comm_layout)

        # Port, baud rate, flow control, escaped config grid layout
        comm_options_layout = QGridLayout()
        comm_layout.addLayout(comm_options_layout)

        port_label = QLabel("Port")
        comm_options_layout.addWidget(port_label, 0, 0)

        baud_label = QLabel("Baud")
        comm_options_layout.addWidget(baud_label, 1, 0)

        flow_label = QLabel("Flow Control")
        comm_options_layout.addWidget(flow_label, 2, 0)

        api_label = QLabel("API Mode")
        comm_options_layout.addWidget(api_label, 3, 0)

        port_combo = QComboBox()
        comm_options_layout.addWidget(port_combo, 0, 1)

        baud_combo = QComboBox()
        baud_combo.addItems(list(map(str, constants.BAUD_RATES)))
        comm_options_layout.addWidget(baud_combo, 1, 1)

        flow_check = QCheckBox("Enable")
        comm_options_layout.addWidget(flow_check, 2, 1)

        api_mode_combo = QComboBox()
        api_mode_combo.addItem("API Escaped")
        api_mode_combo.addItem("API Unescaped")
        comm_options_layout.addWidget(api_mode_combo, 3, 1)

        # Option setters
        port_combo.currentTextChanged.connect(lambda val: self.xbee.set_port(val))
        baud_combo.currentTextChanged.connect(lambda val: self.xbee.set_baud(int(val)))
        flow_check.stateChanged.connect(lambda val: self.xbee.set_flow_control(val))
        api_mode_combo.currentTextChanged.connect(lambda val: self.xbee.set_api_escaped(val == "API Escaped"))

        # QSettings getters
        port_combo.addItems(self.xbee.get_available_ports())
        if settings.value("comm/port", "COM3") in self.xbee.get_available_ports():
            port_combo.setCurrentText(settings.value("comm/port", "COM3")) # type: ignore
        baud_combo.setCurrentText(str(settings.value("comm/baud", 230400, type=int)))
        flow_check.setChecked(settings.value("comm/fc", False, type=bool)) # type: ignore
        api_mode_combo.setCurrentText(settings.value("comm/escaped", False, type=bool) and "API Escaped" or "API Unescaped") # type: ignore

        # QSettings setters
        port_combo.currentTextChanged.connect(lambda val: settings.setValue("comm/port", val))
        baud_combo.currentTextChanged.connect(lambda val: settings.setValue("comm/baud", int(val)))
        flow_check.stateChanged.connect(lambda val: settings.setValue("comm/fc", val == 2))
        api_mode_combo.currentTextChanged.connect(lambda val: settings.setValue("comm/escaped", val == "API Escaped"))

        return layout

    @staticmethod
    def update_logs(log_area: QTextEdit):
        for _ in range(dc_log_queue.qsize()):
            log_area.append(log_converter.convert("\033[91mDESKTOP CLIENT >>>\033[0m " + dc_log_queue.get().strip()))

    def export_logs(self, log_area: QTextEdit):
        name = QFileDialog.getSaveFileName(self,
                                           'Export Logs',
                                           filter="Plain Text (*.txt);;Colored HTML Document (*.html);;Markdown (*.md)")
        if name[0]:
            with open(name[0], "w") as file:
                if name[1] == "Colored HTML Document (*.html)":
                    file.write(log_area.toHtml())
                elif name[1] == "Markdown (*.md)":
                    file.write(log_area.toMarkdown())
                else:
                    file.write(log_area.toPlainText())


    def set_theme(self, theme: str):
        self.settings.setValue("window/theme", theme)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.settings.setValue("window/x", self.geometry().x())
        self.settings.setValue("window/y", self.geometry().y())
        if not self.isMaximized():
            self.settings.setValue("window/width", self.geometry().width())
            self.settings.setValue("window/height", self.geometry().height())
        event.accept()

def controller_backend():
    try:
        begin_controller_backend()
    except RuntimeError as e:
        logger.error(f"Error in controller backend: {repr(e)}")
        controller_backend()

if __name__ == "__main__":
    # Log queue and ansi2html converter
    dc_log_queue = queue.Queue()
    log_converter = ansi2html.Ansi2HTMLConverter()
    log_converter.scheme = "osx"
    logger.add(dc_log_queue.put, colorize=True)

    logger.info(f"Using Qt: {qVersion()}")
    logger.info(f"Using pyglet: {controllers.pyglet.version}")
    logger.info(f"Using Python: {platform.python_version()}")
    logger.info(f"Kevinbot Desktop Client: {__version__}")

    threading.Thread(target=controller_backend, daemon=True).start()
    logger.debug("Pyglet backend started in thread")

    app = QApplication(sys.argv)
    app.setApplicationVersion(__version__)
    app.setApplicationName("Kevinbot Desktop Client")
    win = MainWindow()
    logger.debug("Executing app gui")
    app.exec()