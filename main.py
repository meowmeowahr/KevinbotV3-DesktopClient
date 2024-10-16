import queue
import sys
import os
import platform
import threading
import time
from typing import Tuple
from dataclasses import dataclass

from loguru import logger

import pyglet
import qdarktheme as qtd
import qtawesome as qta
from PySide6.QtCore import (
    QSize,
    QSettings,
    qVersion,
    Qt,
    QTimer,
    QCoreApplication,
    Signal,
    QCommandLineParser,
    QBuffer,
    QIODevice,
)
from PySide6.QtGui import QIcon, QCloseEvent, QPixmap, QFont, QFontDatabase
from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QMainWindow,
    QWidget,
    QApplication,
    QTabWidget,
    QToolBox,
    QLabel,
    QRadioButton,
    QSplitter,
    QTextEdit,
    QPushButton,
    QFileDialog,
    QGridLayout,
    QComboBox,
    QCheckBox,
    QErrorMessage,
    QScrollArea,
    QMessageBox,
    QSlider,
    QFrame,
    QLineEdit,
    QToolButton,
    QDockWidget,
)
from Custom_Widgets.QCustomModals import QCustomModals

import ansi2html
import shortuuid

import xbee

from enums import Cardinal
from ui.util import add_tabs
from ui.widgets import WarningBar, CustomTabWidget, AuthorWidget, ColorBlock
from ui.plots import BatteryGraph, StickVisual, PovVisual
from ui.mjpeg import MJPEGViewer

from components import controllers, ControllerManagerWidget, begin_controller_backend
from components.xbee import XBeeManager

import constants

__version__ = "0.0.0"
__authors__ = [
    {
        "name": "Kevin Ahr",
        "email": "meowmeowahr@gmail.com",
        "website": "https://github.com/meowmeowahr",
        "title": "Primary Developer",
    },
]


@dataclass
class StateManager:
    connected: bool = False
    waiting_for_handshake: bool = False
    estop: bool = False
    enabled: bool = False
    id: str = ""
    tick_speed: float | None = None
    camera_address: str = "http://kevinbot.local"
    last_system_tick: float = time.time()
    last_core_tick: float = time.time()
    left_power: float = 0.0
    right_power: float = 0.0


class MainWindow(QMainWindow):
    left_stick_update = Signal(pyglet.input.Controller, float, float)
    right_stick_update = Signal(pyglet.input.Controller, float, float)
    pov_update = Signal(pyglet.input.Controller, bool, bool, bool, bool)

    def __init__(self, app: QApplication | QCoreApplication, dc_log_queue: queue.Queue):
        super().__init__()
        self.setWindowTitle(f"Kevinbot Desktop Client {__version__}")
        self.setWindowIcon(QIcon("assets/icons/icon.svg"))
        self.setDockOptions(QMainWindow.DockOption.AnimatedDocks) # No tabs in docks

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

        self.state.camera_address = self.settings.value("comm/camera_address", "http://10.0.0.1:5000/video_feed", type=str)  # type: ignore
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

        # Timers
        self.logger_timer = QTimer()
        self.handshake_timer = QTimer()
        self.handshake_timer.setInterval(1500)
        self.handshake_timer.timeout.connect(self.handshake_timeout_handler)

        self.tick_timer = QTimer()
        self.tick_timer.setInterval(1000)
        self.tick_timer.timeout.connect(self.tick_checker)
        self.tick_timer.start()

        self.controller_timer = QTimer()
        self.controller_timer.setInterval(1000)
        self.controller_timer.timeout.connect(self.controller_checker)
        self.controller_timer.start()

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
        self.controller_manager.on_disconnected.connect(
            self.controller_disconnected_handler
        )
        self.controller_manager.on_refresh.connect(self.controller_refresh_handler)

        self.left_stick_update.connect(self.update_left_stick_visuals)
        self.right_stick_update.connect(self.update_right_stick_visuals)
        self.pov_update.connect(self.update_dpad_visuals)

        # Drive
        self.state.left_power = 0
        self.state.right_power = 0

        self.left_stick_update.connect(self.drive_left)
        self.right_stick_update.connect(self.drive_right)

        # Communications
        self.xbee = XBeeManager(
            self.settings.value("comm/port", ""),
            self.settings.value("comm/baud", 921600, type=int),  # type: ignore
            self.settings.value("comm/fc", False, type=bool),  # type: ignore
            self.settings.value("comm/escaped", False, type=bool),  # type: ignore
        )
        self.xbee.on_error.connect(self.serial_error_handler)
        self.xbee.on_reject.connect(self.serial_reject_handler)
        self.xbee.on_open.connect(self.serial_open_handler)
        self.xbee.on_close.connect(self.serial_close_handler)
        self.xbee.on_data.connect(self.serial_data_handler)

        # Tabs
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

        tabs: list[Tuple[str, QIcon]] = [
            ("Main", QIcon("assets/icons/icon.svg")),
            ("Connections", qta.icon("mdi6.transit-connection-variant")),
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
        self.state_dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures | QDockWidget.DockWidgetFeature.DockWidgetMovable)
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
        self.battery_dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures | QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetClosable)
        self.addDockWidget(Qt.DockWidgetArea.TopDockWidgetArea, self.battery_dock)

        self.battery_widget = QWidget()
        self.battery_dock.setWidget(self.battery_widget)

        self.battery_layout = QHBoxLayout()
        self.battery_widget.setLayout(self.battery_layout)

        # Battery
        self.battery_graphs = []
        self.battery_volt_labels = []
        for i in range(2):
            graph = BatteryGraph()
            graph.setFixedSize(QSize(100, 64))
            self.battery_graphs.append(graph)

            label = QLabel(f"Battery {i+1}")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            volt = QLabel("Unknown")
            volt.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.battery_volt_labels.append(volt)

            layout = QVBoxLayout()
            layout.addWidget(graph)
            layout.addWidget(label)
            layout.addWidget(volt)

            self.battery_layout.addLayout(layout)

        self.state_bar.addStretch()
        
        self.indicators_dock = QDockWidget("Indicators")
        self.indicators_dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures | QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetClosable)
        self.addDockWidget(Qt.DockWidgetArea.TopDockWidgetArea, self.indicators_dock)

        self.indicators_widget = QWidget()
        self.indicators_dock.setWidget(self.indicators_widget)

        self.indicators_grid = QGridLayout()
        self.indicators_widget.setLayout(self.indicators_grid)

        self.serial_indicator_led = ColorBlock()
        self.serial_indicator_led.set_color("#f44336")
        self.indicators_grid.addWidget(self.serial_indicator_led, 0, 0)

        self.systick_indicator_led = ColorBlock()
        self.systick_indicator_led.set_color("#f44336")
        self.indicators_grid.addWidget(self.systick_indicator_led, 1, 0)

        self.coretick_indicator_led = ColorBlock()
        self.coretick_indicator_led.set_color("#f44336")
        self.indicators_grid.addWidget(self.coretick_indicator_led, 2, 0)

        self.controller_led = ColorBlock()
        self.controller_led.set_color("#f44336")
        self.indicators_grid.addWidget(self.controller_led, 3, 0)

        self.serial_indicator_label = QLabel("Serial")
        self.indicators_grid.addWidget(self.serial_indicator_label, 0, 1)

        self.systick_indicator_label = QLabel("Sys Tick")
        self.indicators_grid.addWidget(self.systick_indicator_label, 1, 1)

        self.coretick_indicator_led_label = QLabel("Core Tick")
        self.indicators_grid.addWidget(self.coretick_indicator_led_label, 2, 1)

        self.controller_indicator_label = QLabel("Controller")
        self.indicators_grid.addWidget(self.controller_indicator_label, 3, 1)

        self.state_label = QLabel("No Communications")
        self.state_label.setFont(
            QFont(self.fontInfo().family(), 16, weight=QFont.Weight.DemiBold)
        )
        self.state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.state_layout.addWidget(self.state_label)

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
            self.port_combo,
            self.serial_connect_button,
            self.stick_visual_left,
            self.stick_visual_right,
            self.pov_visual,
        ) = self.connection_layout(self.settings)
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

        self.right_tabs.addTab(
            QWidget(), qta.icon("mdi6.robot-industrial"), "Arms && Head"
        )
        self.right_tabs.addTab(
            QWidget(), qta.icon("mdi6.led-strip-variant"), "Lighting"
        )
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
        xcb_check.setChecked(self.settings.value("platform/force_xcb", type=bool)) # type: ignore
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

        hide_sys_details = QLabel(
            "Hiding system ports will hide ports beginning with /dev/ttyS*"
        )
        comm_layout.addWidget(hide_sys_details)

        hide_sys_ports = QCheckBox("Hide System Ports")
        hide_sys_ports.setChecked(settings.value("comm/hide_sys_ports", False, type=bool))  # type: ignore
        hide_sys_ports.clicked.connect(
            lambda: self.set_hide_sys_ports(hide_sys_ports.isChecked())
        )
        comm_layout.addWidget(hide_sys_ports)

        cam_addr_details = QLabel("IP Address (preferred) or host of MJPEG FPV stream")
        comm_layout.addWidget(cam_addr_details)

        camera_input = QLineEdit()
        camera_input.setText(self.settings.value("comm/camera_address", "http://10.0.0.1:5000/video_feed", type=str))  # type: ignore
        camera_input.textChanged.connect(
            lambda: self.set_camera_address(camera_input.text())
        )
        comm_layout.addWidget(camera_input)

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
        log_level.setValue(list(log_level_map.keys())[list(log_level_map.values()).index(settings.value("logging/level", 20, type=int))])  # type: ignore
        log_level.valueChanged.connect(lambda: set_log_level(log_level.value()))
        logging_layout.addWidget(log_level)

        log_level_name = QLabel(log_level_names[settings.value("logging/level", 20, type=int)])  # type: ignore
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

    def connection_layout(self, settings: QSettings):
        layout = QHBoxLayout()

        splitter = QSplitter()
        layout.addWidget(splitter)

        # Controller
        controller_widget = QWidget()
        splitter.addWidget(controller_widget)

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

        # Comm
        comm_widget = QWidget()
        splitter.addWidget(comm_widget)

        comm_layout = QVBoxLayout()
        comm_widget.setLayout(comm_layout)

        # Port, baud rate, flow control, escaped config grid layout
        comm_options_layout = QGridLayout()
        comm_options_layout.setColumnStretch(1, 1)
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
        comm_options_layout.addWidget(port_combo, 0, 1, 1, 2)

        baud_combo = QComboBox()
        baud_combo.addItems(list(map(str, constants.BAUD_RATES)))
        comm_options_layout.addWidget(baud_combo, 1, 1, 1, 2)

        flow_check = QCheckBox("Enable")
        comm_options_layout.addWidget(flow_check, 2, 1, 1, 2)

        api_mode_combo = QComboBox()
        api_mode_combo.addItem("API Escaped")
        api_mode_combo.addItem("API Unescaped")
        comm_options_layout.addWidget(api_mode_combo, 3, 1, 1, 2)

        refresh_ports_button = QPushButton("Refresh")
        refresh_ports_button.setIcon(qta.icon("mdi6.refresh"))
        refresh_ports_button.clicked.connect(self.reload_ports)
        comm_options_layout.addWidget(refresh_ports_button, 4, 2)

        connect_button = QPushButton("Connect")
        connect_button.setIcon(qta.icon("mdi6.wifi"))
        connect_button.clicked.connect(self.open_connection)
        comm_options_layout.addWidget(connect_button, 4, 1)

        # Option setters
        port_combo.currentTextChanged.connect(lambda val: self.xbee.set_port(val))
        baud_combo.currentTextChanged.connect(lambda val: self.xbee.set_baud(int(val)))
        flow_check.stateChanged.connect(lambda val: self.xbee.set_flow_control(val))
        api_mode_combo.currentTextChanged.connect(
            lambda val: self.xbee.set_api_escaped(val == "API Escaped")
        )

        # QSettings getters
        port_combo.addItems(
            self.xbee.get_available_ports(
                not self.settings.value("comm/hide_sys_ports", False, type=bool)
            )
        )
        if settings.value("comm/port", "COM3") in self.xbee.get_available_ports(
            not self.settings.value("comm/hide_sys_ports", False)
        ):
            port_combo.setCurrentText(settings.value("comm/port", "COM3"))  # type: ignore
        if port_combo.count() == 0:
            connect_button.setEnabled(False)
        baud_combo.setCurrentText(str(settings.value("comm/baud", 230400, type=int)))
        flow_check.setChecked(settings.value("comm/fc", False, type=bool))  # type: ignore
        api_mode_combo.setCurrentText(settings.value("comm/escaped", False, type=bool) and "API Escaped" or "API Unescaped")  # type: ignore

        # QSettings setters
        port_combo.currentTextChanged.connect(
            lambda val: settings.setValue("comm/port", val)
        )
        baud_combo.currentTextChanged.connect(
            lambda val: settings.setValue("comm/baud", int(val))
        )
        flow_check.stateChanged.connect(
            lambda val: settings.setValue("comm/fc", val == 2)
        )
        api_mode_combo.currentTextChanged.connect(
            lambda val: settings.setValue("comm/escaped", val == "API Escaped")
        )

        return (
            layout,
            port_combo,
            connect_button,
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
        name_text.setStyleSheet(
            "font-size: 30px; font-weight: bold; font-family: Roboto;"
        )
        name_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(name_text)

        version = QLabel(f"Version {__version__}")
        version.setStyleSheet(
            "font-size: 24px; font-weight: semibold; font-family: Roboto;"
        )
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(version)

        qt_version = QLabel("Qt Version: " + qVersion())
        qt_version.setStyleSheet(
            "font-size: 22px; font-weight: normal; font-family: Roboto;"
        )
        qt_version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(qt_version)

        tabs = CustomTabWidget()
        tabs.icon_size = QSize(32, 32)
        layout.addWidget(tabs)

        # Authors
        authors_scroll = QScrollArea()
        authors_scroll.setWidgetResizable(True)
        tabs.addTab(authors_scroll, "Authors", qta.icon("mdi6.account-multiple"))

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

        for license in [
            ("Desktop Client", "LICENSE"),
            ("Roboto Font", "assets/fonts/Roboto/LICENSE.txt"),
            ("JetBrains Mono Font", "assets/fonts/JetBrains_Mono/OFL.txt"),
        ]:

            license_viewer = QTextEdit()
            license_viewer.setReadOnly(True)
            try:
                with open(license[1], "r") as file:
                    license_viewer.setText(file.read())
            except FileNotFoundError:
                buffer = QBuffer()
                buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                qta.icon("mdi6.alert", color="#f44336").pixmap(QSize(64, 64)).save(buffer, "PNG")
                encoded = buffer.data().toBase64().toStdString()
                license_viewer.setText(f"<img src=\"data:image/png;base64, {encoded}\" alt=\"Red dot\"/><br>"
                                       f"License file '{license[1]}' not found.<br>There was an error locating the license file. "
                                       "A copy of it should be included in the source and binary distributions.")
            licenses_tabs.addTab(license_viewer, license[0])

        tabs.addTab(licenses_tabs, "License", qta.icon("mdi6.gavel"))

        aboutqt = QToolButton()
        aboutqt.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        aboutqt.clicked.connect(QApplication.aboutQt)
        aboutqt.setIconSize(tabs.icon_size)
        aboutqt.setIcon(qta.icon("mdi6.code-block-tags"))
        aboutqt.setText("About Qt")
        tabs.tab_buttons.append(aboutqt)
        tabs.tab_buttons_layout.addWidget(aboutqt)

        return layout

    # State
    def request_estop(self):
        self.xbee.broadcast("kevinbot.request.estop")

    def request_enable(self, enable: bool):
        self.xbee.broadcast(f"kevinbot.request.enable={enable}")

    # Logging
    def update_logs(self, log_area: QTextEdit):
        for _ in range(self.dc_log_queue.qsize()):
            log_area.append(
                self.log_converter.convert(
                    "\033[91mDESKTOP CLIENT >>>\033[0m "
                    + self.dc_log_queue.get().strip()
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

    # Serial
    def reload_ports(self):
        previous_port = self.port_combo.currentText()
        self.port_combo.clear()
        self.port_combo.addItems(
            self.xbee.get_available_ports(
                not self.settings.value("comm/hide_sys_ports", False, type=bool)
            )
        )
        if previous_port in self.xbee.get_available_ports(
            not self.settings.value("comm/hide_sys_ports", False, type=bool)
        ):
            self.port_combo.setCurrentText(previous_port)

        if self.port_combo.count() == 0:
            self.serial_connect_button.setEnabled(False)
        else:
            self.serial_connect_button.setEnabled(True)

    def set_hide_sys_ports(self, hide: bool):
        self.settings.setValue("comm/hide_sys_ports", hide)
        self.reload_ports()

    def serial_error_handler(self, error: str):
        self.state.connected = False

        logger.error(f"Serial error: {error}")

        msg = QErrorMessage(self)
        msg.setWindowTitle("Serial Error")
        msg.showMessage(f"Serial Error: {error}")
        msg.exec()

        self.state_label.setText("No Communications")

    def pulse_state_label(self):
        if self.state_label_timer_runs == 5:
            self.state_label_timer_runs = 0
            self.state_label_timer.stop()
            self.state_label.setStyleSheet("")
            return
        if self.state_label.styleSheet() == "color: #f44336;":
            self.state_label.setStyleSheet("")
        else:
            self.state_label.setStyleSheet("color: #f44336;")
        self.state_label_timer_runs += 1

    def serial_reject_handler(self):
        if not self.state.connected:
            if not self.state_label_timer.isActive():
                self.state_label_timer.start(100)
        else:
            logger.error(
                "Something went seriously wrong, causing a command to be rejected"
            )

    def serial_open_handler(self):
        self.state.connected = True
        self.serial_connect_button.setText("Disconnect")
        self.serial_indicator_led.set_color("#4caf50")

        self.state.last_system_tick = time.time()
        self.state.last_core_tick = time.time()

        logger.success("Serial port opened")

    def serial_close_handler(self):
        self.state.connected = False
        self.state.waiting_for_handshake = False
        self.serial_connect_button.setText("Connect")
        self.serial_indicator_led.set_color("#f44336")

        logger.debug("Serial port closed")

        if not self.state.estop:
            self.state_label.setText("No Communications")

    # * Serial Data Recieve
    def serial_data_handler(self, data: dict):
        logger.trace(f"Received packet: {data}")
        command: str = data["rf_data"].decode("utf-8").split("=", 1)[0]
        if len(data["rf_data"].decode("utf-8").split("=", 1)) > 1:
            value: str | None = data["rf_data"].decode("utf-8").split("=", 1)[1]
        else:
            value = None

        match command:
            case "connection.handshake.end":
                if value == f"DC_{self.state.id}":
                    self.state.waiting_for_handshake = False
                    # There is no need to set the status label, since the handshake includes an enable message
            case "system.estop":
                self.state.estop = True
                self.state_label.setText("Emergency Stopped")
                self.xbee.close()
            case "kevinbot.enabled":
                self.state.enabled = value in [
                    "True",
                    "true",
                    "1",
                    "on",
                    "ON",
                    "enabled",
                    "ENABLED",
                ]
                self.state_label.setText(
                    "Robot Enabled" if self.state.enabled else "Robot Disabled"
                )
            case "system.tick.speed":
                if not value:
                    return

                try:
                    tick = float(value)
                except ValueError:
                    tick = None

                self.state.tick_speed = tick
            case "system.uptime":
                self.state.last_system_tick = time.time()
            case "core.uptime":
                self.state.last_core_tick = time.time()
            case "bms.voltages":
                if not value:
                    return

                for index, i in enumerate(value.split(",")):
                    self.battery_volt_labels[index].setText(f"{int(i)/10}v")
                    self.battery_graphs[index].add(int(i) / 10)

    # * Drive
    def drive_left(self, controller: pyglet.input.Controller, xvalue, yvalue):
        if (not self.state.connected) or self.state.waiting_for_handshake:
            return

        if controller == self.controller_manager.get_controllers()[0]:
            if round(self.state.left_power * 100) == (
                round(yvalue * 100)
                if abs(yvalue) > constants.CONTROLLER_DEADBAND
                else 0
            ):
                return
            if abs(yvalue) > constants.CONTROLLER_DEADBAND:
                self.state.left_power = yvalue
            else:
                self.state.left_power = 0
            self.xbee.broadcast(
                f"drive={round(self.state.left_power*100)},{round(self.state.right_power*100)}"
            )

    def drive_right(self, controller: pyglet.input.Controller, xvalue, yvalue):
        if (not self.state.connected) or self.state.waiting_for_handshake:
            return

        if controller == self.controller_manager.get_controllers()[0]:
            if round(self.state.right_power * 100) == (
                round(yvalue * 100)
                if abs(yvalue) > constants.CONTROLLER_DEADBAND
                else 0
            ):
                return
            if abs(yvalue) > constants.CONTROLLER_DEADBAND:
                self.state.right_power = yvalue
            else:
                self.state.right_power = 0
            self.xbee.broadcast(
                f"drive={round(self.state.left_power*100)},{round(self.state.right_power*100)}"
            )

    def open_connection(self):
        if self.state.connected:
            self.end_communication()
            return
        self.xbee.open()
        self.state.waiting_for_handshake = True
        self.begin_handshake()

    def end_communication(self):
        if self.state.connected:
            self.xbee.broadcast(
                f"connection.disconnect=DC_{self.state.id}|{__version__}|kevinbot.dc"
            )
            self.xbee.close()
            logger.info("Communication ended")

    def begin_handshake(self):
        if self.state.connected:
            self.state_label.setText("Awaiting Handshake")
            self.handshake_timer.start()

    def handshake_timeout_handler(self):
        if not self.state.connected:
            self.handshake_timer.stop()
            return

        if self.state.waiting_for_handshake:
            self.xbee.broadcast(
                f"connection.connect=DC_{self.state.id}|{__version__}|kevinbot.dc"
            )
        else:
            self.handshake_timer.stop()

    # * Background checks
    def tick_checker(self):
        if self.state.connected:
            if self.state.tick_speed:
                if time.time() - self.state.last_core_tick > self.state.tick_speed:
                    self.coretick_indicator_led.set_color("#f44336")
                else:
                    self.coretick_indicator_led.set_color("#4caf50")

                if time.time() - self.state.last_system_tick > self.state.tick_speed:
                    self.systick_indicator_led.set_color("#f44336")
                else:
                    self.systick_indicator_led.set_color("#4caf50")
            else:
                logger.warning("No tick speed set, skipping tick check")

    def controller_checker(self):
        if len(self.controller_manager.get_controller_ids()) > 0:
            self.controller_led.set_color("#4caf50")
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
            modalIcon=qta.icon("mdi6.information", color="#0f0f0f").pixmap(
                QSize(32, 32)
            ),
            closeIcon=qta.icon("mdi6.close", color="#0f0f0f").pixmap(QSize(32, 32)),
            duration=3000,
        )
        modal.setStyleSheet(
            "* { border: none; background-color: #b3e5fc; color: #0f0f0f; }"
        )
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
            modalIcon=qta.icon("mdi6.alert-decagram", color="#0f0f0f").pixmap(
                QSize(32, 32)
            ),
            closeIcon=qta.icon("mdi6.close", color="#0f0f0f").pixmap(QSize(32, 32)),
            duration=3000,
        )
        modal.setStyleSheet(
            "* { border: none; background-color: #ffecb3; color: #0f0f0f; }"
        )
        modal.setParent(self)
        modal.show()

    def controller_stick_action(
        self,
        controller: pyglet.input.Controller,
        stick: str,
        xvalue: float,
        yvalue: float,
    ):
        if (
            controller == self.controller_manager.get_controllers()[0]
            and stick == "leftstick"
        ):
            self.left_stick_update.emit(controller, xvalue, yvalue)
        elif (
            controller == self.controller_manager.get_controllers()[0]
            and stick == "rightstick"
        ):
            self.right_stick_update.emit(controller, xvalue, yvalue)

    def controller_dpad_action(
        self,
        controller: pyglet.input.Controller,
        left: bool,
        down: bool,
        right: bool,
        up: bool,
    ):
        if controller == self.controller_manager.get_controllers()[0]:
            self.pov_update.emit(controller, left, down, right, up)

    def update_left_stick_visuals(
        self, controller: pyglet.input.Controller, xvalue: float, yvalue: float
    ):
        if controller != self.controller_manager.get_controllers()[0]:
            return

        if self.tabs.currentIndex() == 1:
            self.stick_visual_left.plot(
                xvalue,
                yvalue,
            )

    def update_right_stick_visuals(
        self, controller: pyglet.input.Controller, xvalue: float, yvalue: float
    ):
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
        dpleft: bool,
        dpright: bool,
        dpup: bool,
        dpdown: bool,
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

    def set_xcb(self, xcb: bool):
        self.settings.setValue("platform/force_xcb", xcb)

    def set_camera_address(self, host: str):
        self.settings.setValue("comm/camera_address", host)
        self.state.camera_address = host
        self.fpv.mjpeg_thread.stream_url = host

    def closeEvent(self, event: QCloseEvent) -> None:
        self.setDisabled(True)

        self.fpv.mjpeg_thread.terminate()
        self.fpv.mjpeg_thread.wait()

        if self.state.connected:
            msg = QMessageBox(self)
            msg.setWindowTitle("Close while Connected?")
            msg.setText(
                "Are you sure you want to close the application while connected?"
            )
            msg.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            msg.setIcon(QMessageBox.Icon.Question)
            result = msg.exec()
            if result == QMessageBox.StandardButton.No:
                self.setDisabled(False)
                event.ignore()
                return

        self.end_communication()
        self.xbee.halt()
        
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
        logger.error(f"Error in controller backend: {repr(e)}")
        controller_backend()


def main(app: QApplication | None = None):
    # Log queue and ansi2html converter
    dc_log_queue: queue.Queue[str] = queue.Queue()

    settings = QSettings("meowmeowahr", "KevinbotDesktopClient")
    logger.remove()
    logger.add(sys.stdout, colorize=True, level=settings.value("logging/level", 20, type=int))  # type: ignore
    logger.add(dc_log_queue.put, colorize=True, level=settings.value("logging/level", 20, type=int))  # type: ignore

    if not app:
        if platform.system() == "Linux":
            if settings.value("platform/force_xcb", False, type=bool):
                os.environ["QT_QPA_PLATFORM"] = "xcb"
                logger.debug("Forcing XCB Qt Platform")
        app = QApplication(sys.argv)
        app.setApplicationVersion(__version__)
        app.setWindowIcon(QIcon("assets/icons/icon.svg"))
        app.setApplicationName("Kevinbot Desktop Client")
        app.setStyle(
            "Fusion"
        )  # helps avoid problems in the future, make sure everyone is usign the same base

    parse(app)

    logger.info(f"Using Qt: {qVersion()}")
    logger.info(f"Using pyglet: {controllers.pyglet.version}")
    logger.info(f"Using Python: {platform.python_version()}")
    logger.info(f"Using xbee-python: {xbee.__version__}")
    logger.info(f"Kevinbot Desktop Client: {__version__}")

    threading.Thread(target=controller_backend, daemon=True).start()
    logger.debug("Pyglet backend started in thread")

    QFontDatabase.addApplicationFont("assets/fonts/Roboto/Roboto-Regular.ttf")
    QFontDatabase.addApplicationFont("assets/fonts/Roboto/Roboto-Medium.ttf")
    QFontDatabase.addApplicationFont("assets/fonts/Roboto/Roboto-Bold.ttf")
    QFontDatabase.addApplicationFont(
        "assets/fonts/JetBrains_Mono/static/JetBrainsMono-Regular.ttf"
    )

    MainWindow(app, dc_log_queue)
    logger.debug("Executing app gui")
    app.exec()


if __name__ == "__main__":
    main()
