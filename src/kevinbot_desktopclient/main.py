from functools import partial
import os
import platform
import queue
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import override

import ansi2html
import kevinbotlib
import kevinbotlib.exceptions
import pyglet
import qdarktheme as qtd
import qtawesome as qta
import shortuuid
from Custom_Widgets.QCustomModals import QCustomModals
from loguru import logger
from PySide6.QtCore import (
    QBuffer,
    QCommandLineParser,
    QCoreApplication,
    QIODevice,
    QObject,
    QRunnable,
    QSettings,
    QSize,
    Qt,
    QThreadPool,
    QTimer,
    Signal,
    Slot,
    qVersion,
)
from PySide6.QtGui import QCloseEvent, QFont, QFontDatabase, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDockWidget,
    QErrorMessage,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QToolBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from kevinbot_desktopclient import constants
from kevinbot_desktopclient.components import (
    ControllerManagerWidget,
    PingWorker,
    begin_controller_backend,
    controllers,
)
from kevinbot_desktopclient.components.dataplot import LivePlot
from kevinbot_desktopclient.components.ping import PingWidget
from kevinbot_desktopclient.enums import Cardinal
from kevinbot_desktopclient.ui.mjpeg import MJPEGViewer
from kevinbot_desktopclient.ui.plots import BatteryGraph, PovVisual, StickVisual
from kevinbot_desktopclient.ui.util import add_tabs
from kevinbot_desktopclient.ui.widgets import AuthorWidget, ColorBlock, CustomTabWidget, WarningBar

__version__ = "0.0.0"
__authors__ = [
    {
        "name": "Kevin Ahr",
        "email": "meowmeowahr@gmail.com",
        "website": "https://github.com/meowmeowahr",
        "title": "Primary Developer",
    },
]


class AppState(Enum):
    NO_COMMUNICATIONS = 1
    CONNECTING = 2
    WAITING_FOR_HANDSHAKE = 3
    CONNECTED = 4
    ESTOPPED = 5
    DISCONNECTING = 6


@dataclass
class StateManager:
    app_state: AppState = AppState.NO_COMMUNICATIONS
    enabled: bool = False
    id: str = ""
    tick_speed: float | None = None
    camera_address: str = "http://kevinbot.local"
    mqtt_host: str = "http://10.0.0.1/"
    mqtt_port: int = 1883
    last_system_tick: float = field(default_factory=lambda: time.time())
    last_core_tick: float = field(default_factory=lambda: time.time())
    left_power: float = 0.0
    right_power: float = 0.0


class WorkerSignals(QObject):
    # Define custom signals to emit status
    connection_status = Signal(str)
    connection_error = Signal(Exception, traceback.FrameSummary)
    robot_connected = Signal()
    robot_disconnected = Signal()


class ConnectionWorker(QRunnable):
    def __init__(
        self,
        robot: kevinbotlib.MqttKevinbot,
        settings,
        state,
        state_label,
        serial_connect_button,
    ):
        super().__init__()
        self.robot = robot
        self.settings = settings
        self.state = state
        self.state_label = state_label
        self.serial_connect_button = serial_connect_button
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        # This code will now run in a separate thread
        if self.robot.connected:
            logger.info("Communication ending")
            self.robot.callback = None
            self.robot.disconnect()
            self.signals.robot_disconnected.emit()
        else:
            try:
                self.robot.connect(
                    "kevinbot",
                    self.settings.value("comm/host", "http://10.0.0.1/"),
                    self.settings.value("comm/mqtt_port", 1883),
                )
            except (
                UnicodeError,
                ConnectionRefusedError,
                kevinbotlib.exceptions.HandshakeTimeoutException,
            ) as e:
                logger.error(f"Failed to connect to MQTT broker: {e!r}")
                self.signals.connection_error.emit(e, traceback.format_exc())
                return

            self.signals.connection_status.emit("Awaiting Handshake")
            self.signals.robot_connected.emit()


class MainWindow(QMainWindow):
    left_stick_update = Signal(pyglet.input.Controller, float, float)
    right_stick_update = Signal(pyglet.input.Controller, float, float)
    pov_update = Signal(pyglet.input.Controller, bool, bool, bool, bool)

    def __init__(self, app: QApplication | QCoreApplication, dc_log_queue: queue.Queue):
        super().__init__()
        self.setWindowTitle(f"Kevinbot Desktop Client {__version__}")
        self.setWindowIcon(QIcon("assets/icons/icon.svg"))
        self.setDockOptions(QMainWindow.DockOption.AnimatedDocks)  # No tabs in docks

        self.dc_log_queue = dc_log_queue
        self.log_converter = ansi2html.Ansi2HTMLConverter()
        self.log_converter.scheme = "osx"

        # Settings Manager
        self.settings = QSettings("meowmeowahr", "KevinbotDesktopClient", self)

        # Remembered position
        if self.settings.contains("window/x"):
            # noinspection PyTypeChecker
            self.setGeometry(
                self.settings.value("window/x", type=int),  # type: ignore
                self.settings.value("window/y", type=int),  # type: ignore
                self.settings.value("window/width", type=int),  # type: ignore
                self.settings.value("window/height", type=int),  # type: ignore
            )

        # State Manager
        self.state = StateManager()
        self.state.id = shortuuid.uuid()
        logger.info(f"Desktop Client ID is {self.state.id}")

        self.state.camera_address = self.settings.value(
            "comm/camera_address", "http://10.0.0.1:5000/video_feed", type=str
        )  # type: ignore
        self.state.mqtt_host = self.settings.value("comm/host", "http://10.0.0.1/", type=str)  # type: ignore
        logger.info(f"Robot FPV MJPEG Host: {self.state.camera_address}")

        # Theme
        theme = self.settings.value("window/theme", "dark", type=str)
        if theme == "dark":
            qtd.setup_theme(
                "dark",
                additional_qss="#warning_bar_text{color: #050505;} *{font-family: Roboto;}",
                custom_colors=constants.CUSTOM_COLORS_DARK,
            )
            qta.dark(app)
        elif theme == "light":
            qtd.setup_theme("light")
            qta.light(app)
        else:
            qtd.setup_theme(
                "auto",
                additional_qss="#warning_bar_text{color: #050505;}",
                custom_colors=constants.CUSTOM_COLORS_DARK,
            )

        # Communications
        self.robot = kevinbotlib.MqttKevinbot()
        self.robot.callback = self.update_states
        self.drive = kevinbotlib.Drivebase(self.robot)

        # Timers
        self.logger_timer = QTimer()

        self.controller_timer = QTimer()
        self.controller_timer.setInterval(1000)
        self.controller_timer.timeout.connect(self.controller_checker)
        self.controller_timer.start()

        self.battery_timer = QTimer()
        self.battery_timer.setInterval(750)
        self.battery_timer.timeout.connect(self.battery_update)
        self.battery_timer.start()

        # Thread pool
        self.thread_pool = QThreadPool()

        # Widget/Root Layout
        self.root_widget = QWidget()
        self.setCentralWidget(self.root_widget)

        self.root_layout = QVBoxLayout()
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_widget.setLayout(self.root_layout)

        # Controller
        self.controller_manager = ControllerManagerWidget(slots=1)

        for controller in self.controller_manager.controllers:
            controllers.map_stick(controller, self.controller_stick_action)
            controllers.map_pov(controller, self.controller_dpad_action)

        self.controller_manager.on_connected.connect(self.controller_connected_handler)
        self.controller_manager.on_disconnected.connect(self.controller_disconnected_handler)
        self.controller_manager.on_refresh.connect(self.controller_refresh_handler)

        self.left_stick_update.connect(self.update_left_stick_visuals)
        self.right_stick_update.connect(self.update_right_stick_visuals)
        self.pov_update.connect(self.update_dpad_visuals)

        self.ping_worker = PingWorker(
            self.settings.value("comm/host", "http://10.0.0.1/", type=str),  # type: ignore
            self.settings.value("ping/burst_count", 3, type=int),  # type: ignore
            self.settings.value("ping/burst_interval", 0.3, type=int),  # type: ignore
            self.settings.value("ping/timeout", 1, type=int),  # type: ignore
        )

        self.ping_timer = QTimer()
        self.ping_timer.timeout.connect(self.ping_worker.start)
        self.ping_timer.setInterval(self.settings.value("ping/interval", 4, type=int))  # type: ignore
        self.ping_timer.start()

        # * Drive
        self.state.left_power = 0
        self.state.right_power = 0

        self.left_stick_update.connect(self.drivecmd)
        self.right_stick_update.connect(self.drivecmd)

        # * Tabs
        self.tabs = QTabWidget()
        self.tabs.setIconSize(QSize(36, 36))
        self.tabs.setTabPosition(QTabWidget.TabPosition.West)
        self.tabs.setObjectName("root_tabs")
        self.tabs.setStyleSheet(
            "#root_tabs::pane {"
            "border-right: none;"
            "border-top: none;"
            "border-bottom: none;"
            "border-radius: 0px; }"
            "#root_tabs > QTabBar::tab {"
            "padding-top: -12px;"
            "margin-bottom: 6px;"
            "margin-bottom: 6px;"
            "}"
            "#root_tabs::tab-bar {"
            "alignment: center;"
            "}"
        )
        self.root_layout.addWidget(self.tabs)

        tabs: list[tuple[str, QIcon]] = [
            ("Main", QIcon("assets/icons/icon.svg")),
            ("Controllers", qta.icon("mdi6.controller")),
            ("Debug", qta.icon("mdi6.bug")),
            ("Settings", qta.icon("mdi6.cog")),
            ("About", qta.icon("mdi6.information-slab-circle")),
        ]
        (
            self.main,
            self.connection_widget,
            self.debug,
            self.settings_widget,
            self.about_widget,
        ) = add_tabs(self.tabs, tabs)

        # * Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.ping_widget = PingWidget()
        self.ping_worker.ping_completed.connect(self.ping_widget.set_values)
        self.status_bar.addPermanentWidget(self.ping_widget)

        # * Main Tab
        self.main_layout = QVBoxLayout()
        self.main.setLayout(self.main_layout)

        self.setStyleSheet(
            "#enable_button, #disable_button, #estop_button {"
            "font-size: 24px;"
            "font-weight: bold;"
            "color: #212121;"
            "}"
            "#enable_button {"
            "background-color: #00C853;"
            "}"
            "#disable_button {"
            "background-color: #EF5350;"
            "}"
            "#estop_button {"
            "background-color: #FF9722;"
            "}"
        )

        # * State Bar
        self.state_dock = QDockWidget("State")
        self.state_dock.setFeatures(
            QDockWidget.DockWidgetFeature.NoDockWidgetFeatures | QDockWidget.DockWidgetFeature.DockWidgetMovable
        )
        self.addDockWidget(Qt.DockWidgetArea.TopDockWidgetArea, self.state_dock)

        self.state_widget = QWidget()
        self.state_dock.setWidget(self.state_widget)

        self.state_layout = QVBoxLayout()
        self.state_widget.setLayout(self.state_layout)

        self.state_bar = QHBoxLayout()
        self.state_layout.addLayout(self.state_bar)

        self.state_bar.addStretch()

        self.enable_button = QPushButton("Enable".upper())
        self.enable_button.setObjectName("enable_button")
        self.enable_button.setFixedSize(QSize(200, 64))
        self.enable_button.setShortcut(Qt.Key.Key_Apostrophe)
        self.enable_button.clicked.connect(lambda: self.request_enable(True))
        self.state_bar.addWidget(self.enable_button)

        self.disable_button = QPushButton("Disable".upper())
        self.disable_button.setObjectName("disable_button")
        self.disable_button.setFixedSize(QSize(200, 64))
        self.disable_button.setShortcut(Qt.Key.Key_Return)
        self.disable_button.clicked.connect(lambda: self.request_enable(False))
        self.state_bar.addWidget(self.disable_button)

        self.state_bar.addStretch()

        self.estop_button = QPushButton("E-Stop".upper())
        self.estop_button.setObjectName("estop_button")
        self.estop_button.setFixedSize(QSize(340, 64))
        self.estop_button.setShortcut(Qt.Key.Key_Space)
        self.estop_button.pressed.connect(self.request_estop)
        self.state_bar.addWidget(self.estop_button)

        self.state_bar.addStretch()

        self.battery_dock = QDockWidget("Batteries")
        self.battery_dock.setFeatures(
            QDockWidget.DockWidgetFeature.NoDockWidgetFeatures
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.addDockWidget(Qt.DockWidgetArea.TopDockWidgetArea, self.battery_dock)

        self.battery_widget = QWidget()
        self.battery_dock.setWidget(self.battery_widget)

        self.battery_layout = QHBoxLayout()
        self.battery_widget.setLayout(self.battery_layout)

        # * Battery
        self.battery_graphs: list[BatteryGraph] = []
        self.battery_volt_labels = []
        for i in range(2):
            graph = BatteryGraph()
            graph.setFixedSize(QSize(100, 64))
            self.battery_graphs.append(graph)

            label = QLabel(f"Battery {i+1}")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            volt = QLabel("Unknown")
            volt.setFont(QFont(self.font().family(), 15))
            volt.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.battery_volt_labels.append(volt)

            layout = QVBoxLayout()
            layout.addWidget(graph)
            layout.addWidget(label)
            layout.addWidget(volt)

            self.battery_layout.addLayout(layout)

        self.state_bar.addStretch()

        # * Indicators

        self.indicators_dock = QDockWidget("Indicators")
        self.indicators_dock.setFeatures(
            QDockWidget.DockWidgetFeature.NoDockWidgetFeatures
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.addDockWidget(Qt.DockWidgetArea.TopDockWidgetArea, self.indicators_dock)

        self.indicators_widget = QWidget()
        self.indicators_dock.setWidget(self.indicators_widget)

        self.indicators_grid = QGridLayout()
        self.indicators_widget.setLayout(self.indicators_grid)

        self.connect_indicator_led = ColorBlock()
        self.connect_indicator_led.set_color("#f44336")
        self.indicators_grid.addWidget(self.connect_indicator_led, 0, 0)

        self.systick_indicator_led = ColorBlock()
        self.systick_indicator_led.set_color("#f44336")
        self.indicators_grid.addWidget(self.systick_indicator_led, 1, 0)

        self.coretick_indicator_led = ColorBlock()
        self.coretick_indicator_led.set_color("#f44336")
        self.indicators_grid.addWidget(self.coretick_indicator_led, 2, 0)

        self.controller_led = ColorBlock()
        self.controller_led.set_color("#f44336")
        self.indicators_grid.addWidget(self.controller_led, 3, 0)

        self.connect_indicator_label = QLabel("Connected")
        self.indicators_grid.addWidget(self.connect_indicator_label, 0, 1)

        self.systick_indicator_label = QLabel("Sys Tick")
        self.indicators_grid.addWidget(self.systick_indicator_label, 1, 1)

        self.coretick_indicator_led_label = QLabel("Core Tick")
        self.indicators_grid.addWidget(self.coretick_indicator_led_label, 2, 1)

        self.controller_indicator_label = QLabel("Controller")
        self.indicators_grid.addWidget(self.controller_indicator_label, 3, 1)

        # * Plot
        self.add_plot()

        self.state_label = QLabel("No Communications")
        self.state_label.setFont(QFont(self.fontInfo().family(), 16, weight=QFont.Weight.DemiBold))
        self.state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.state_layout.addWidget(self.state_label)

        self.connect_button = QPushButton("Connect")
        self.connect_button.setIcon(qta.icon("mdi6.wifi"))
        self.connect_button.clicked.connect(self.toggle_connection)
        self.state_layout.addWidget(self.connect_button)

        self.state_label_timer = QTimer()
        self.state_label_timer.timeout.connect(self.pulse_state_label)
        self.state_label_timer_runs = 0

        hline = QFrame()
        hline.setFrameShape(QFrame.Shape.HLine)
        hline.setFrameShadow(QFrame.Shadow.Sunken)
        hline.setFixedHeight(2)
        self.main_layout.addWidget(hline)

        self.settings_widget.setLayout(self.settings_layout(self.settings))
        self.debug.setLayout(self.debug_layout(self.settings))
        (
            self.comm_layout,
            self.stick_visual_left,
            self.stick_visual_right,
            self.pov_visual,
        ) = self.connection_layout()
        self.connection_widget.setLayout(self.comm_layout)
        self.about_widget.setLayout(self.about_layout())

        # * Main Split View
        self.splitter = QSplitter()
        self.splitter.setOrientation(Qt.Orientation.Horizontal)
        self.main_layout.addWidget(self.splitter, 2)

        # * FPV

        self.left_split = QWidget()
        self.splitter.addWidget(self.left_split)
        self.splitter.setCollapsible(0, False)

        self.left_split_layout = QVBoxLayout()
        self.left_split.setLayout(self.left_split_layout)

        self.fpv_control_layout = QHBoxLayout()
        self.left_split_layout.addLayout(self.fpv_control_layout)

        self.fpv_refresh = QPushButton()
        self.fpv_refresh.setIcon(qta.icon("mdi6.reload"))
        self.fpv_refresh.setIconSize(QSize(24, 24))
        self.fpv_refresh.setFixedSize(QSize(32, 32))
        self.fpv_control_layout.addWidget(self.fpv_refresh)

        self.fpv_control_layout.addStretch()

        self.fpv_fps = QLabel("?? FPS")
        self.fpv_control_layout.addWidget(self.fpv_fps)

        self.fpv = MJPEGViewer(self.state.camera_address)
        self.fpv_refresh.clicked.connect(self.reload_fpv)
        self.fpv_last_frame = time.time()
        self.fpv.mjpeg_thread.frame_received.connect(self.fpv_new_frame)
        self.left_split_layout.addWidget(self.fpv, 2)

        # * Main View

        self.right_tabs = QTabWidget()
        self.right_tabs.setIconSize(QSize(24, 24))
        self.splitter.addWidget(self.right_tabs)

        self.right_tabs.addTab(QWidget(), qta.icon("mdi6.robot-industrial"), "Arms && Head")
        self.right_tabs.addTab(QWidget(), qta.icon("mdi6.led-strip-variant"), "Lighting")
        self.right_tabs.addTab(QWidget(), qta.icon("mdi6.eye"), "Eyes")
        self.right_tabs.addTab(QWidget(), qta.icon("mdi.text-to-speech"), "Speech")
        self.right_tabs.addTab(QWidget(), qta.icon("mdi6.cogs"), "System")

        self.show()

    def fpv_new_frame(self):
        self.fpv_fps.setText(f"{round(1 / (time.time() - self.fpv_last_frame))} FPS")
        self.fpv_last_frame = time.time()

    def reload_fpv(self):
        self.fpv.mjpeg_thread.terminate()
        self.fpv.mjpeg_thread.start()

    def add_plot(self, title="Plot"):
        self.plot_dock = QDockWidget("Plot")
        self.plot_dock.setFeatures(
            QDockWidget.DockWidgetFeature.NoDockWidgetFeatures
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.plot_dock)

        self.plot_widget = QWidget()
        self.plot_dock.setWidget(self.plot_widget)

        self.plot_layout = QVBoxLayout()
        self.plot_widget.setLayout(self.plot_layout)

        self.plot = LivePlot()
        self.plot_layout.addWidget(self.plot)

        self.plot.add_data_source("IMU/Gyro/Yaw", lambda _: self.robot.get_state().imu.gyro[0], "r")
        self.plot.add_data_source("IMU/Gyro/Pitch", lambda _: self.robot.get_state().imu.gyro[1], "g")
        self.plot.add_data_source("IMU/Gyro/Roll", lambda _: self.robot.get_state().imu.gyro[2], "b")

        self.plot.add_data_source("IMU/Accel/Yaw", lambda _: self.robot.get_state().imu.accel[0], "m")
        self.plot.add_data_source("IMU/Accel/Pitch", lambda _: self.robot.get_state().imu.accel[1], "c")
        self.plot.add_data_source("IMU/Accel/Roll", lambda _: self.robot.get_state().imu.accel[2], "y")

        for i in range(len(self.robot.get_state().battery.voltages)):
            self.plot.add_data_source(f"Battery/Voltage{i+1}", partial(lambda _, idx=i: self.robot.get_state().battery.voltages[idx]), ['r', 'g', 'b', 'm'][i%3])

        self.plot.add_data_source("Enviro/Temp", lambda _: self.robot.get_state().enviro.temperature, "#e91e63")
        self.plot.add_data_source("Enviro/Humi", lambda _: self.robot.get_state().enviro.humidity, "#3f51b5")
        self.plot.add_data_source("Enviro/Pres", lambda _: self.robot.get_state().enviro.pressure, "#cddc39")

        self.plot.add_data_source("Thermo/LeftMotor", lambda _: self.robot.get_state().thermal.left_motor, "#ff9800")
        self.plot.add_data_source("Thermo/RightMotor", lambda _: self.robot.get_state().thermal.right_motor, "#607d8b")
        self.plot.add_data_source("Thermo/Interval", lambda _: self.robot.get_state().thermal.internal, "#03a9f4")

        self.plot.add_data_source("Drive/LeftTarget", lambda _: self.robot.get_state().motion.left_power, "#ff5722")
        self.plot.add_data_source("Drive/RightTarget", lambda _: self.robot.get_state().motion.right_power, "#2196f3")

        self.plot.add_data_source("Drive/LeftAmps", lambda _: self.robot.get_state().motion.amps[0], "#8bc34a")
        self.plot.add_data_source("Drive/RightAmps", lambda _: self.robot.get_state().motion.amps[1], "#673ab7")

        self.plot.add_data_source("Drive/LeftWatts", lambda _: self.robot.get_state().motion.watts[0], "#795548")
        self.plot.add_data_source("Drive/RightWatts", lambda _: self.robot.get_state().motion.watts[1], "#009688")

    def settings_layout(self, settings: QSettings):
        layout = QVBoxLayout()

        toolbox = QToolBox()
        layout.addWidget(toolbox)

        system_widget = QWidget()
        toolbox.addItem(system_widget, "System")

        system_layout = QVBoxLayout()
        system_widget.setLayout(system_layout)

        system_warning = WarningBar("Restart required to apply theme")
        system_layout.addWidget(system_warning)

        xcb_check = QCheckBox("Force XCB Platform on Linux")
        xcb_check.setChecked(self.settings.value("platform/force_xcb", type=bool))  # type: ignore
        xcb_check.clicked.connect(lambda: self.set_xcb(xcb_check.isChecked()))
        system_layout.addWidget(xcb_check)

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

        # Communications
        comm_widget = QWidget()
        toolbox.addItem(comm_widget, "Communication")

        comm_layout = QVBoxLayout()
        comm_widget.setLayout(comm_layout)

        cam_addr_details = QLabel("IP Address (preferred) or host of MJPEG FPV stream")
        comm_layout.addWidget(cam_addr_details)

        camera_input = QLineEdit()
        camera_input.setText(
            self.settings.value(
                "comm/camera_address",
                "http://10.0.0.1:5000/video_feed",
                type=str,  # type: ignore
            )
        )
        camera_input.textChanged.connect(lambda: self.set_camera_address(camera_input.text()))
        comm_layout.addWidget(camera_input)

        mqtt_host_defails = QLabel("IP Address (preferred) or host of KevinbotLib MQTT Interface")
        comm_layout.addWidget(mqtt_host_defails)

        mqtt_host_input = QLineEdit()
        mqtt_host_input.setText(
            self.settings.value("comm/host", "http://10.0.0.1/", type=str)  # type: ignore
        )
        mqtt_host_input.textChanged.connect(lambda: self.set_mqtt_host(mqtt_host_input.text()))
        comm_layout.addWidget(mqtt_host_input)

        # Logging
        logging_widget = QWidget()
        toolbox.addItem(logging_widget, "Logging")

        logging_layout = QVBoxLayout()
        logging_widget.setLayout(logging_layout)

        logging_warning = WarningBar("Restart required to apply logging level")
        logging_layout.addWidget(logging_warning)

        log_level_label = QLabel("Level")
        logging_layout.addWidget(log_level_label)

        log_level_map = {
            0: 5,
            1: 10,
            2: 20,
            3: 25,
            4: 30,
            5: 40,
            6: 50,
        }

        log_level_names = {
            5: "TRACE",
            10: "DEBUG",
            20: "INFO",
            25: "SUCCESS",
            30: "WARNING",
            40: "ERROR",
            50: "CRITICAL",
        }

        log_level = QSlider(Qt.Orientation.Horizontal)
        log_level.setMinimum(0)
        log_level.setMaximum(6)
        log_level.setTickPosition(QSlider.TickPosition.TicksBelow)
        log_level.setTickInterval(1)
        log_level.setValue(
            list(log_level_map.keys())[
                list(log_level_map.values()).index(
                    settings.value("logging/level", 20, type=int)  # type: ignore
                )
            ]
        )
        log_level.valueChanged.connect(lambda: set_log_level(log_level.value()))
        logging_layout.addWidget(log_level)

        log_level_name = QLabel(
            log_level_names[settings.value("logging/level", 20, type=int)]  # type: ignore
        )
        log_level_name.setFont(QFont(self.fontInfo().family(), 22))
        logging_layout.addWidget(log_level_name)

        if settings.value("window/theme", "dark") == "dark":
            theme_dark.setChecked(True)
        elif settings.value("window/theme", "dark") == "light":
            theme_light.setChecked(True)
        else:
            theme_system.setChecked(True)

        theme_dark.clicked.connect(lambda: self.set_theme("dark"))
        theme_light.clicked.connect(lambda: self.set_theme("light"))
        theme_system.clicked.connect(lambda: self.set_theme("system"))

        def set_log_level(level: int):
            settings.setValue("logging/level", log_level_map[level])
            log_level_name.setText(log_level_names[log_level_map[level]])

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

    def connection_layout(self):
        layout = QHBoxLayout()

        # Controller
        controller_widget = QWidget()
        layout.addWidget(controller_widget)

        controller_layout = QHBoxLayout()
        controller_widget.setLayout(controller_layout)

        controller_left_layout = QVBoxLayout()
        controller_layout.addLayout(controller_left_layout)

        controller_help = WarningBar(
            "The first controller in the list will be the active controller.\n"
            "Drag-and-Drop controllers to select the active one"
        )
        controller_left_layout.addWidget(controller_help)

        controller_left_layout.addWidget(self.controller_manager)

        controller_right_layout = QVBoxLayout()
        controller_layout.addLayout(controller_right_layout)

        # Joystick visuals
        left_stick_visual = StickVisual()
        left_stick_visual.setFixedSize(QSize(100, 100))
        left_stick_visual.plot(0, 0)
        controller_right_layout.addWidget(left_stick_visual)

        right_stick_visual = StickVisual()
        right_stick_visual.setFixedSize(QSize(100, 100))
        right_stick_visual.plot(0, 0)
        controller_right_layout.addWidget(right_stick_visual)

        pov_visual = PovVisual()
        pov_visual.setFixedSize(QSize(100, 100))
        pov_visual.plot(Cardinal.CENTER)
        controller_right_layout.addWidget(pov_visual)

        return (
            layout,
            left_stick_visual,
            right_stick_visual,
            pov_visual,
        )

    def about_layout(self):
        layout = QHBoxLayout()

        left_layout = QVBoxLayout()
        layout.addLayout(left_layout)

        icon_layout = QHBoxLayout()
        left_layout.addLayout(icon_layout)

        icon = QLabel()
        icon.setPixmap(QPixmap("assets/icons/icon.svg"))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setScaledContents(True)
        icon.setFixedSize(QSize(160, 160))
        icon_layout.addWidget(icon)

        name_text = QLabel("Kevinbot Desktop Client")
        name_text.setStyleSheet("font-size: 30px; font-weight: bold; font-family: Roboto;")
        name_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(name_text)

        version = QLabel(f"Version {__version__}")
        version.setStyleSheet("font-size: 24px; font-weight: semibold; font-family: Roboto;")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(version)

        qt_version = QLabel("Qt Version: " + qVersion())
        qt_version.setStyleSheet("font-size: 22px; font-weight: normal; font-family: Roboto;")
        qt_version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(qt_version)

        tabs = CustomTabWidget()
        tabs.icon_size = QSize(32, 32)
        layout.addWidget(tabs)

        # Authors
        authors_scroll = QScrollArea()
        authors_scroll.setWidgetResizable(True)
        tabs.add_tab(authors_scroll, "Authors", qta.icon("mdi6.account-multiple"))

        authors_widget = QWidget()
        authors_scroll.setWidget(authors_widget)

        authors_layout = QVBoxLayout()
        authors_widget.setLayout(authors_layout)

        for author in __authors__:
            author_widget = AuthorWidget()
            author_widget.author_name = author["name"]
            author_widget.author_title = author["title"]
            author_widget.author_email = author["email"]
            author_widget.author_website = author["website"]
            authors_layout.addWidget(author_widget)

        # License

        licenses_tabs = QTabWidget()
        licenses_tabs.setContentsMargins(100, 100, 100, 100)

        for component_license in [
            ("Desktop Client", "LICENSE"),
            ("Roboto Font", "assets/fonts/Roboto/LICENSE.txt"),
            ("JetBrains Mono Font", "assets/fonts/JetBrains_Mono/OFL.txt"),
        ]:
            license_viewer = QTextEdit()
            license_viewer.setReadOnly(True)
            try:
                with open(component_license[1]) as file:
                    license_viewer.setText(file.read())
            except FileNotFoundError:
                buffer = QBuffer()
                buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                qta.icon("mdi6.alert", color="#f44336").pixmap(QSize(64, 64)).save(buffer, "PNG")
                encoded = buffer.data().toBase64().toStdString()
                license_viewer.setText(
                    f'<img src="data:image/png;base64, {encoded}" alt="Red dot"/><br>'
                    f"License file '{component_license[1]}' not found.<br>There was an error locating the license file. "
                    "A copy of it should be included in the source and binary distributions."
                )
            licenses_tabs.addTab(license_viewer, component_license[0])

        tabs.add_tab(licenses_tabs, "License", qta.icon("mdi6.gavel"))

        aboutqt = QToolButton()
        aboutqt.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        aboutqt.clicked.connect(QApplication.aboutQt)
        aboutqt.setIconSize(tabs.icon_size)
        aboutqt.setIcon(qta.icon("mdi6.code-block-tags"))
        aboutqt.setText("About Qt")
        tabs.tab_buttons.append(aboutqt)
        tabs.tab_buttons_layout.addWidget(aboutqt)

        return layout

    # Enable / E-Stop
    def request_estop(self):
        if self.state.app_state in [AppState.ESTOPPED, AppState.NO_COMMUNICATIONS]:
            if not self.state_label_timer.isActive():
                self.state_label_timer.start(100)
            return

        self.robot.e_stop()
        self.state.app_state = AppState.ESTOPPED
        self.state_label.setText("Emergency Stopped")

    def request_enable(self, enable: bool):  # noqa: FBT001
        """Attempt to enable or disable the robot.

        Args:
            enable (bool): Enable or disable
        """
        if self.state.app_state in [
            AppState.ESTOPPED,
            AppState.NO_COMMUNICATIONS,
            AppState.WAITING_FOR_HANDSHAKE,
            AppState.CONNECTING,
        ]:
            if not self.state_label_timer.isActive():
                self.state_label_timer.start(100)
            return

        if enable:
            self.robot.request_enable()
        else:
            self.robot.request_disable()

    # Logging
    def update_logs(self, log_area: QTextEdit):
        for _ in range(self.dc_log_queue.qsize()):
            log_area.append(
                self.log_converter.convert(
                    "\033[91mDESKTOP CLIENT >>>\033[0m " + self.dc_log_queue.get().strip()
                ).replace(
                    "display: inline; white-space: pre-wrap; word-wrap: break-word;",  # ? Is there a better way to do this?
                    "display: inline; white-space: pre-wrap; word-wrap: break-word; font-family: JetBrains Mono;",
                )
            )

    def export_logs(self, log_area: QTextEdit):
        name = QFileDialog.getSaveFileName(
            self,
            "Export Logs",
            filter="Plain Text (*.txt);;Colored HTML Document (*.html);;Markdown (*.md)",
        )
        if name[0]:
            with open(name[0], "w") as file:
                if name[1] == "Colored HTML Document (*.html)":
                    file.write(log_area.toHtml())
                elif name[1] == "Markdown (*.md)":
                    file.write(log_area.toMarkdown())
                else:
                    file.write(log_area.toPlainText())

    # Connection
    def pulse_state_label(self):
        if self.state_label_timer_runs == constants.STATE_LABEL_PULSE_COUNT:
            self.state_label_timer_runs = 0
            self.state_label_timer.stop()
            self.state_label.setStyleSheet("")
            return
        if self.state_label.styleSheet() == "color: #f44336;":
            self.state_label.setStyleSheet("")
        else:
            self.state_label.setStyleSheet("color: #f44336;")
        self.state_label_timer_runs += 1

    # * Drive
    def drivecmd(self, controller: pyglet.input.Controller, _xvalue, _yvalue):
        if self.state.app_state in [
            AppState.ESTOPPED,
            AppState.NO_COMMUNICATIONS,
            AppState.WAITING_FOR_HANDSHAKE,
            AppState.CONNECTING,
        ]:
            return

        if controller == self.controller_manager.get_controllers()[0]:

            def apply_scaled_deadband(val, *, invert: bool = True):
                if abs(val) < constants.CONTROLLER_DEADBAND:
                    return 0
                val = (
                    val * ((1 + constants.CONTROLLER_DEADBAND) if val > 0 else (1 + constants.CONTROLLER_DEADBAND))
                ) + (-constants.CONTROLLER_DEADBAND if val > 0 else constants.CONTROLLER_DEADBAND)
                return -val if invert else val

            left_power = max(-1, min(1, apply_scaled_deadband(controller.lefty)))
            right_power = max(-1, min(1, apply_scaled_deadband(controller.righty)))
            if round(left_power, 2) == round(self.state.left_power, 2) and round(right_power, 2) == round(
                self.state.right_power, 2
            ):
                return
            self.state.left_power = left_power
            self.state.right_power = right_power

            self.drive.drive_at_power(self.state.left_power, self.state.right_power)

    def toggle_connection(self):
        if self.state.app_state == AppState.ESTOPPED:
            if not self.state_label_timer.isActive():
                self.state_label_timer.start(100)
            return
        self.connect_button.setEnabled(False)  # prevent spamming

        if self.state.app_state == AppState.NO_COMMUNICATIONS:
            self.state.app_state = AppState.CONNECTING
            self.state_label.setText("Connecting")
        else:
            self.state.app_state = AppState.DISCONNECTING

        # Create a worker instance
        worker = ConnectionWorker(self.robot, self.settings, self.state, self.state_label, self.connect_button)
        worker.signals.connection_status.connect(self.state_label.setText)
        worker.signals.robot_connected.connect(self.on_connect)
        worker.signals.connection_error.connect(self.on_connect_error)
        worker.signals.robot_disconnected.connect(self.on_disconnect)

        # Run the worker using the thread pool
        self.thread_pool.start(worker)

    def on_disconnect(self):
        self.state.app_state = AppState.NO_COMMUNICATIONS
        self.state_label.setText("No Communications")
        self.connect_button.setText("Connect")
        self.connect_indicator_led.set_color("#f44336")
        self.connect_button.setEnabled(True)

        for label in self.battery_volt_labels:
            label.setText("Unknown")

    def on_connect(self):
        self.robot.callback = self.update_states
        self.state.app_state = AppState.CONNECTED
        self.connect_indicator_led.set_color("#4caf50")
        self.connect_button.setText("Disconnect")
        self.connect_button.setEnabled(True)

    def on_connect_error(self, _exception: Exception, summary: traceback.FrameSummary):
        self.connect_button.setEnabled(True)
        self.state.app_state = AppState.NO_COMMUNICATIONS
        self.state_label.setText("No Communications")

        # error message
        msg = QErrorMessage(self)
        msg.setWindowTitle("Connection Error")
        msg.showMessage(f"{str(summary).replace('\n', '<br>')}")

    # * Robot state
    def update_states(self, _topics: list[str], _value: str):
        if self.state.app_state != AppState.CONNECTED:
            return

        if self.robot.get_state().enabled:
            self.state_label.setText("Robot Enabled")
        else:
            self.state_label.setText("Robot Disabled")

    def battery_update(self):
        """Update battery states"""
        if self.robot.connected:
            for index, graph in enumerate(self.battery_graphs):
                graph.add(self.robot.get_state().battery.voltages[index])
            for index, label in enumerate(self.battery_volt_labels):
                label.setText(f"{self.robot.get_state().battery.voltages[index]}v")

    def controller_checker(self):
        if len(self.controller_manager.get_controller_ids()) > 0:
            self.controller_led.set_color("#4caf50")
            if self.controller_manager.connected_list.count() == 0:
                self.controller_manager.refresh_controllers()
        else:
            self.controller_led.set_color("#f44336")

    # Controller
    def controller_connected_handler(self, controller: pyglet.input.Controller):
        controllers.map_stick(controller, self.controller_stick_action)
        controllers.map_pov(controller, self.controller_dpad_action)
        logger.success(f"Controller connected: {controller.name}")
        modal = QCustomModals.InformationModal(
            title="Controllers",
            parent=self.main,
            position="top-right",
            description="Controller has been connected",
            isClosable=True,
            modalIcon=qta.icon("mdi6.information", color="#0f0f0f").pixmap(QSize(32, 32)),
            closeIcon=qta.icon("mdi6.close", color="#0f0f0f").pixmap(QSize(32, 32)),
            duration=3000,
        )
        modal.setStyleSheet("* { border: none; background-color: #b3e5fc; color: #0f0f0f; }")
        modal.setParent(self)
        modal.show()

    def controller_refresh_handler(self, controller: list[pyglet.input.Controller]):
        logger.debug("Controllers refreshed")
        for con in controller:
            controllers.map_stick(con, self.controller_stick_action)
            logger.debug(f"Mapped controller sticks: {con.name}")

    def controller_disconnected_handler(self, controller: pyglet.input.Controller):
        logger.warning(f"Controller disconnected: {controller.name}")
        modal = QCustomModals.InformationModal(
            title="Controllers",
            parent=self.main,
            position="top-right",
            description="Controller has disconnected",
            isClosable=True,
            modalIcon=qta.icon("mdi6.alert-decagram", color="#0f0f0f").pixmap(QSize(32, 32)),
            closeIcon=qta.icon("mdi6.close", color="#0f0f0f").pixmap(QSize(32, 32)),
            duration=3000,
        )
        modal.setStyleSheet("* { border: none; background-color: #ffecb3; color: #0f0f0f; }")
        modal.setParent(self)
        modal.show()

    def controller_stick_action(
        self,
        controller: pyglet.input.Controller,
        stick: str,
        xvalue: float,
        yvalue: float,
    ):
        if controller == self.controller_manager.get_controllers()[0] and stick == "leftstick":
            self.left_stick_update.emit(controller, xvalue, yvalue)
        elif controller == self.controller_manager.get_controllers()[0] and stick == "rightstick":
            self.right_stick_update.emit(controller, xvalue, yvalue)

    def controller_dpad_action(
        self,
        controller: pyglet.input.Controller,
        left: bool,  # noqa: FBT001
        down: bool,  # noqa: FBT001
        right: bool,  # noqa: FBT001
        up: bool,  # noqa: FBT001
    ):
        if controller == self.controller_manager.get_controllers()[0]:
            self.pov_update.emit(controller, left, down, right, up)

    def update_left_stick_visuals(self, controller: pyglet.input.Controller, xvalue: float, yvalue: float):
        if controller != self.controller_manager.get_controllers()[0]:
            return

        if self.tabs.currentIndex() == 1:
            self.stick_visual_left.plot(
                xvalue,
                yvalue,
            )

    def update_right_stick_visuals(self, controller: pyglet.input.Controller, xvalue: float, yvalue: float):
        if controller != self.controller_manager.get_controllers()[0]:
            return

        if self.tabs.currentIndex() == 1:
            self.stick_visual_right.plot(
                xvalue,
                yvalue,
            )

    def update_dpad_visuals(
        self,
        controller: pyglet.input.Controller,
        dpleft: bool,  # noqa: FBT001
        dpright: bool,  # noqa: FBT001
        dpup: bool,  # noqa: FBT001
        dpdown: bool,  # noqa: FBT001
    ):
        if controller != self.controller_manager.get_controllers()[0]:
            return

        if self.tabs.currentIndex() == 1:
            direction_map = {
                (True, False, True, False): Cardinal.NORTHWEST,
                (True, False, False, True): Cardinal.SOUTHWEST,
                (False, True, True, False): Cardinal.NORTHEAST,
                (False, True, False, True): Cardinal.SOUTHEAST,
                (False, False, True, False): Cardinal.NORTH,
                (False, False, False, True): Cardinal.SOUTH,
                (True, False, False, False): Cardinal.WEST,
                (False, True, False, False): Cardinal.EAST,
            }
            cardinal = direction_map.get((dpleft, dpright, dpup, dpdown), Cardinal.CENTER)

            self.pov_visual.plot(cardinal)

    def set_theme(self, theme: str):
        self.settings.setValue("window/theme", theme)

    def set_xcb(self, xcb: bool):  # noqa: FBT001
        self.settings.setValue("platform/force_xcb", xcb)

    def set_camera_address(self, host: str):
        self.settings.setValue("comm/camera_address", host)
        self.state.camera_address = host
        self.fpv.mjpeg_thread.stream_url = host

    def set_mqtt_host(self, host: str):
        self.settings.setValue("comm/host", host)
        self.ping_worker.target = host
        self.state.mqtt_host = host

    @override
    def closeEvent(self, event: QCloseEvent) -> None:
        self.setDisabled(True)
        self.robot.callback = None  # prevent attempting to update deleted Qt widgets

        self.ping_timer.stop()
        self.ping_worker.stop()
        self.ping_worker.wait()

        self.battery_timer.stop()

        self.fpv.mjpeg_thread.terminate()
        self.fpv.mjpeg_thread.wait()

        self.robot.disconnect()

        self.settings.setValue("window/x", self.geometry().x())
        self.settings.setValue("window/y", self.geometry().y())
        if not self.isMaximized():
            self.settings.setValue("window/width", self.geometry().width())
            self.settings.setValue("window/height", self.geometry().height())
        event.accept()


def parse(app):
    """Parse the arguments and options of the given app object."""

    parser = QCommandLineParser()

    parser.addHelpOption()
    parser.addVersionOption()

    parser.process(app)


def controller_backend():  # pragma: no cover
    try:
        begin_controller_backend()
    except RuntimeError as e:
        logger.error(f"Error in controller backend: {e!r}")
        controller_backend()


def main(app: QApplication | None = None):
    # Log queue and ansi2html converter
    dc_log_queue: queue.Queue[str] = queue.Queue()

    settings = QSettings("meowmeowahr", "KevinbotDesktopClient")
    logger.remove()
    logger.add(
        sys.stdout,
        colorize=True,
        level=settings.value("logging/level", 20, type=int),  # type: ignore
    )
    logger.add(
        dc_log_queue.put,
        colorize=True,
        level=settings.value("logging/level", 20, type=int),  # type: ignore
    )

    if not app:
        if platform.system() == "Linux" and settings.value("platform/force_xcb", False, type=bool):
            os.environ["QT_QPA_PLATFORM"] = "xcb"
            logger.debug("Forcing XCB Qt Platform")
        app = QApplication(sys.argv)
        app.setApplicationVersion(__version__)
        app.setWindowIcon(QIcon("assets/icons/icon.svg"))
        app.setApplicationName("Kevinbot Desktop Client")
        app.setStyle("Fusion")  # helps avoid problems in the future, make sure everyone is usign the same base

    parse(app)

    logger.info(f"Using KevinbotLib {kevinbotlib.version}")
    logger.info(f"Using Qt: {qVersion()}")
    logger.info(f"Using pyglet: {controllers.pyglet.version}")
    logger.info(f"Using Python: {platform.python_version()}")
    logger.info(f"Kevinbot Desktop Client: {__version__}")

    threading.Thread(target=controller_backend, daemon=True).start()
    logger.debug("Pyglet backend started in thread")

    QFontDatabase.addApplicationFont("assets/fonts/Roboto/Roboto-Regular.ttf")
    QFontDatabase.addApplicationFont("assets/fonts/Roboto/Roboto-Medium.ttf")
    QFontDatabase.addApplicationFont("assets/fonts/Roboto/Roboto-Bold.ttf")
    QFontDatabase.addApplicationFont("assets/fonts/JetBrains_Mono/static/JetBrainsMono-Regular.ttf")

    MainWindow(app, dc_log_queue)
    logger.debug("Executing app gui")
    app.exec()


if __name__ == "__main__":
    main()
